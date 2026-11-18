import {table} from '../components/common/table.js';
import {badge} from '../components/common/status.js';
import {esc} from '../utils/html.js';
import {download} from '../api/client.js';
import {message} from '../hooks/action.js';
const writes=ws=>ws.length?ws.map(w=>`${esc(w.record)} ← ${esc(w.value)}`).join('<br>'):'—';
const short=sha=>sha?esc(sha.slice(0,12))+'…':'—';
const writeRows=(ws,outcome)=>ws.map(w=>[esc(w.txn||'—'),esc(w.shard),esc(w.record),esc(w.value),outcome]);
function banner(r){
 if(r.error)return `<section class="verdict"><div><p>恢复结论</p><h2>计算失败</h2></div><p>${esc(r.error)}</p></section>`;
 if(r.decision==='recovered')return `<section class="verdict"><div><p>恢复结论</p><h2>${r.verdict==='commit'?'全分片已提交':'全分片已回滚'}</h2></div><p>协调者 ${esc(r.coordinator)} · 新任期 ${r.new_term}<br>落盘裁决 ${esc(r.verdict_record.txn)} / ${esc(r.verdict_record.verdict)} · 摘要 ${short(r.verdict_record.sha256)}</p></section>`;
 if(r.decision==='waiting')return `<section class="verdict"><div><p>恢复结论</p><h2>等待裁决</h2></div><p>新协调者 ${esc(r.coordinator)} 已上任（任期 ${r.new_term}），裁决未落盘<br>${r.stats.waiting} 条争用写入等待中，其余写入照常执行</p></section>`;
 return `<section class="verdict"><div><p>恢复结论</p><h2>安全阻断</h2></div><p>切主未放行，事务保持待决<br>${r.stats.waiting} 条争用写入继续等待</p></section>`;
}
export function txDetailPage(job){if(!job)return '<section class="empty"><h2>还没有恢复演练记录</h2><p>先在事务恢复页提交一条任务，随后可查看恢复证据。</p><a href="#tx">前往事务恢复 →</a></section>';const r=job.result;return `<div class="section-title"><h2>${esc(job.label)} <small>#${job.id}</small></h2>${badge(job.status)}</div>${r?`${banner(r)}<h2>恢复时间线</h2>${table(['步骤','事件','详情'],(r.timeline||[]).map(t=>[t.step,esc(t.event),esc(t.detail)]))}${r.waiting_writes?.length?`<h2>等待中的写入</h2>${table(['事务','分片','记录','新值','结局'],writeRows(r.waiting_writes,r.decision==='recovered'?'已放行执行':'仍在等待'))}`:''}${r.proceeded_writes?.length?`<h2>照常执行的写入</h2>${table(['事务','分片','记录','新值','结局'],writeRows(r.proceeded_writes,'照常执行'))}`:''}<h2>各分片结局</h2>${table(['分片','结局','应用写入','回滚写入','裁决摘要'],(r.shard_outcomes||[]).map(o=>[esc(o.shard),esc(o.state),writes(o.applied),writes(o.rolled_back),short(o.verdict_sha256)]))}<h2>恢复核查</h2>${table(['规则','判定','证据'],(r.checks||[]).map(c=>[esc(c.rule),c.pass?'通过':'阻断',esc(c.evidence)]))}${r.election?`<h2>切主核查（原切主规则）</h2>${table(['规则','判定','证据'],r.election.checks.map(c=>[esc(c.rule),c.pass?'通过':'阻断',esc(c.evidence)]))}<h2>候选节点复核</h2>${table(['节点','日志位置','落后条数','满足候选条件'],r.election.candidates.map(n=>[esc(n.name),n.log_position,n.lag,n.eligible?'是':'否']))}`:''}<p class="checksum">输入摘要 ${esc(r.input_sha256||'无')} · 模型 ${esc(r.model_version||'—')}</p>`:'<p class="notice">后台正在计算，点击刷新获取状态。</p>'}<div class="toolbar"><button id="export">导出冻结输入与结果</button><button class="secondary" id="refresh">刷新状态</button></div><details><summary>查看冻结输入</summary><pre>${esc(JSON.stringify(job.snapshot,null,2))}</pre></details>`;}
export function bindTxDetail(job,render){document.querySelector('#refresh')?.addEventListener('click',render);document.querySelector('#export')?.addEventListener('click',()=>download('tx-drills',job.id).catch(e=>message(e.message,true)));}
