import {store} from '../stores/entities.js';
import {session} from '../stores/session.js';
import {txDrillsAPI} from '../api/entities.js';
import {table} from '../components/common/table.js';
import {badge,txDecision} from '../components/common/status.js';
import {esc,formObject} from '../utils/html.js';
import {action} from '../hooks/action.js';
function parseLines(text,parts,label){
 return String(text||'').split('\n').map(l=>l.trim()).filter(Boolean).map((l,i)=>{
  const p=l.split(/\s+/);
  if(p.length<parts)throw new Error(`${label}第 ${i+1} 行不完整：${l}`);
  return p;
 });
}
export function txPage(){return `<section class="split compact"><div><h2>演练一次协调失联恢复</h2><p>事务在各分片准备完成后协调者失联。快照冻结节点、剧本与全部写入；后台按原切主规则选出新协调者，把同一份裁决落盘后应用到所有分片。</p><p class="big-note">裁决未明，只拦争用同一记录的写入。</p></div>${session.role!=='viewer'?`<form id="tx-form"><label>演练标签<input name="label" value="切主窗口事务恢复" required maxlength="120"></label><label>故障剧本<select name="scenario_id">${store.scenarios.map(s=>`<option value="${s.id}">${esc(s.name)}</option>`).join('')}</select></label><label>事务编号<input name="txn_id" value="txn-1001" required pattern="[a-zA-Z0-9_-]+" maxlength="40"></label><label>准备写入（每行：分片 记录 新值）<textarea name="prepared" required>shard-a acct:1 +100
shard-b acct:2 -100
shard-c acct:3 +40</textarea></label><label>并发写入（裁决未明期间到达，每行：事务 分片 记录 新值）<textarea name="concurrent">txn-2001 shard-a acct:1 -50
txn-2002 shard-c acct:9 +5</textarea></label><div class="fields"><label>裁决<select name="verdict"><option value="commit">commit 提交</option><option value="abort">abort 回滚</option></select></label><label>补送裁决次数<input name="redeliver" type="number" min="0" max="5" value="1" required></label></div><label class="check"><input name="verdict_persisted" type="checkbox" checked> 裁决已落盘（取消则演练裁决未明）</label><label class="check"><input name="crash_after_verdict" type="checkbox"> 落盘后注入中断（验证续跑）</label><button type="submit">冻结快照并入队 →</button></form>`:'<p class="readonly">观察员可复核下方记录。</p>'}</section><div class="section-title"><h2>最近恢复演练</h2><button class="secondary" id="refresh">刷新状态</button></div>${table(['编号','演练','执行状态','事务结局','等待写入','证据'],store.txDrills.map(d=>[d.id,esc(d.label),badge(d.status),txDecision(d.result),d.result?.stats?d.result.stats.waiting+' 条':'—',`<a href="#txdetail/${d.id}">查看记录 →</a>`]))}`;}
export function bindTx(render){document.querySelector('#refresh').onclick=render;action(document.querySelector('#tx-form'),async f=>{const d=formObject(f);d.scenario_id=Number(d.scenario_id);d.redeliver=Number(d.redeliver);d.verdict_persisted=f.elements.verdict_persisted.checked;d.crash_after_verdict=f.elements.crash_after_verdict.checked;d.prepared=parseLines(d.prepared,3,'准备写入').map(p=>({shard:p[0],record:p[1],value:p.slice(2).join(' ')}));if(!d.prepared.length)throw new Error('至少需要一条准备写入');d.concurrent=parseLines(d.concurrent,4,'并发写入').map(p=>({txn:p[0],shard:p[1],record:p[2],value:p.slice(3).join(' ')}));const job=await txDrillsAPI.create(d);location.hash='#txdetail/'+job.id;});}
