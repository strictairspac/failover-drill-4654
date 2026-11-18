import {DRILL_STATUSES,TX_DECISIONS} from '../../constants/enums.js';
import {esc} from '../../utils/html.js';
export const badge=(status)=>`<span class="badge ${esc(status)}">${esc(DRILL_STATUSES[status]||status)}</span>`;
export const txDecision=(r)=>{
 if(!r)return '待计算';
 if(r.error)return '计算失败';
 if(r.decision==='recovered')return r.verdict==='commit'?'全分片已提交':'全分片已回滚';
 return TX_DECISIONS[r.decision]||r.decision;
};
