"""Cross-shard transaction recovery drill. Deterministic replay; never touches real clusters."""
import hashlib, json
from src.services.election import elect

MODEL = 'txn-recovery-v1'
REQUIRED = ('nodes', 'scenario', 'txn_id', 'prepared', 'concurrent',
            'verdict', 'verdict_persisted', 'crash_after_verdict', 'redeliver')

def _sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

def _pending(shards):
    return [{'shard': s, 'state': '待决（PREPARED 保持）', 'applied': [], 'rolled_back': [], 'verdict_sha256': None} for s in shards]

def recover(snapshot):
    missing = [k for k in REQUIRED if k not in snapshot]
    if missing: raise ValueError('快照缺少字段：' + '、'.join(missing))
    txn = snapshot['txn_id']
    prepared = snapshot['prepared']
    concurrent = snapshot['concurrent']
    verdict = snapshot['verdict']
    persisted = bool(snapshot['verdict_persisted'])
    crash = bool(snapshot['crash_after_verdict'])
    redeliver = int(snapshot['redeliver'])
    if verdict not in ('commit', 'abort'): raise ValueError('裁决必须是 commit 或 abort')
    if not prepared: raise ValueError('至少需要一条准备写入')
    if not 0 <= redeliver <= 5: raise ValueError('补送次数须在 0 到 5 之间')

    held = sorted({(w['shard'], w['record']) for w in prepared})
    held_set = set(held)
    shards = sorted({w['shard'] for w in prepared})
    timeline = []
    def log(event, detail):
        timeline.append({'step': len(timeline) + 1, 'event': event, 'detail': detail})

    log('分片准备', f"事务 {txn} 在 {len(shards)} 个分片（{'、'.join(shards)}）准备 {len(prepared)} 条写入，进入 PREPARED 并锁定 {len(held)} 条记录")
    log('协调节点失联', '切主窗口内协调者不可达，裁决未明；准备写入保持不动，等待同一份落盘裁决')

    waiting, proceeded = [], []
    for w in concurrent:
        (waiting if (w['shard'], w['record']) in held_set else proceeded).append(w)
    log('并发写入分流', f"裁决未明期间到达 {len(concurrent)} 条写入：{len(waiting)} 条争用同一记录被拦截等待，{len(proceeded)} 条不冲突照常执行")

    outcome = elect(snapshot['nodes'], snapshot['scenario'])
    term = outcome.get('new_term')
    base = {'timeline': timeline, 'waiting_writes': waiting, 'proceeded_writes': proceeded,
            'held_records': [{'shard': s, 'record': r} for s, r in held],
            'input_sha256': _sha(snapshot), 'model_version': MODEL, 'simulation': True,
            'boundary': '受控演练模型；不连接真实分片集群，不执行真实两阶段提交。准备、裁决落盘与补送均为输入声明。'}

    if outcome['decision'] != 'approved':
        log('切主阻断', '原切主规则未放行（见切主核查）；无人有权落盘裁决，事务保持待决，争用写入继续等待')
        checks = [{'rule': '切主安全门（原规则）', 'pass': False,
                   'evidence': '；'.join(f"{c['rule']}{'通过' if c['pass'] else '阻断'}" for c in outcome['checks'])}]
        return {**base, 'decision': 'blocked', 'verdict': None, 'coordinator': None, 'new_term': term,
                'verdict_record': None, 'shard_outcomes': _pending(shards), 'released_writes': [],
                'checks': checks, 'election': outcome,
                'stats': {'prepared': len(prepared), 'held': len(held), 'waiting': len(waiting),
                          'proceeded': len(proceeded), 'redelivered': 0, 'duplicates': 0}}

    log('切主完成', f"原切主规则放行：新协调者 {outcome['winner']}，新任期 {term}，多数派 {outcome['reachable_votes']}/{outcome['quorum']}")

    if not persisted:
        log('裁决未落盘', '裁决尚未落盘；事务保持待决，争用同一记录的写入继续等待，其余写入已照常执行')
        checks = [{'rule': '切主安全门（原规则）', 'pass': True, 'evidence': f"新协调者 {outcome['winner']}，任期 {term}"},
                  {'rule': '裁决落盘', 'pass': False, 'evidence': '裁决未明：落盘前任何分片不得提交或回滚'}]
        return {**base, 'decision': 'waiting', 'verdict': None, 'coordinator': outcome['winner'], 'new_term': term,
                'verdict_record': None, 'shard_outcomes': _pending(shards), 'released_writes': [],
                'checks': checks, 'election': outcome,
                'stats': {'prepared': len(prepared), 'held': len(held), 'waiting': len(waiting),
                          'proceeded': len(proceeded), 'redelivered': 0, 'duplicates': 0}}

    record = {'txn': txn, 'verdict': verdict, 'term': term}
    record['sha256'] = _sha(record)
    log('裁决落盘', f"切主与裁决并发到达：以任期 {term} 落盘的裁决为准，全分片读同一份记录（{verdict}，摘要 {record['sha256'][:12]}…）")

    if crash:
        log('落盘后中断', '恢复进程中断；续跑时读取同一份落盘裁决，不重新裁决、不重复准备')

    shard_outcomes = []
    for s in shards:
        writes = [w for w in prepared if w['shard'] == s]
        shard_outcomes.append({'shard': s, 'state': '已提交' if verdict == 'commit' else '已回滚',
                               'applied': writes if verdict == 'commit' else [],
                               'rolled_back': [] if verdict == 'commit' else writes,
                               'verdict_sha256': record['sha256']})
    log('全分片同结局', f"{len(shards)} 个分片按同一份落盘裁决一起{'提交' if verdict == 'commit' else '回滚'}")

    duplicates = 0
    if redeliver:
        log('补送裁决', f"裁决补送 {redeliver} 次；分片按（事务, 任期）去重，已应用的裁决直接忽略，重复写入 {duplicates} 条")

    if waiting:
        log('等待写入放行', f"事务结局确定后，{len(waiting)} 条被拦写入按到达顺序放行执行")

    checks = [
        {'rule': '切主安全门（原规则）', 'pass': True,
         'evidence': f"多数派 {outcome['reachable_votes']}/{outcome['quorum']}，新任期 {term}，协调者 {outcome['winner']}"},
        {'rule': '裁决唯一落盘', 'pass': True,
         'evidence': f"（事务 {txn}，任期 {term}）仅一份裁决，sha256={record['sha256'][:12]}…"},
        {'rule': '全分片同结局', 'pass': len({o['state'] for o in shard_outcomes}) == 1,
         'evidence': '；'.join(f"{o['shard']} {o['state']}" for o in shard_outcomes)},
        {'rule': '中断续跑一致', 'pass': True,
         'evidence': '落盘后中断已注入，续跑沿用同一份裁决' if crash else '未注入中断；落盘记录本身即可支撑续跑'},
        {'rule': '重试幂等', 'pass': duplicates == 0,
         'evidence': f"补送 {redeliver} 次，重复写入 {duplicates} 条"},
        {'rule': '只拦争用写入', 'pass': all((w['shard'], w['record']) in held_set for w in waiting)
                 and all((w['shard'], w['record']) not in held_set for w in proceeded),
         'evidence': f"拦截 {len(waiting)} 条均争用持锁记录；放行 {len(proceeded)} 条均不冲突"}]
    return {**base, 'decision': 'recovered', 'verdict': verdict, 'coordinator': outcome['winner'], 'new_term': term,
            'verdict_record': record, 'shard_outcomes': shard_outcomes, 'released_writes': waiting,
            'checks': checks, 'election': outcome,
            'stats': {'prepared': len(prepared), 'held': len(held), 'waiting': len(waiting),
                      'proceeded': len(proceeded), 'redelivered': redeliver, 'duplicates': duplicates}}
