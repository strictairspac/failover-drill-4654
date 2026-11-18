from sqlalchemy import select
from fastapi import HTTPException
from src.models.entities import Scenario, TxDrill
from src.services.node_service import list_nodes
from src.utils.serialize import record

def create_tx_drill(db, payload):
    scenario = db.get(Scenario, payload.scenario_id)
    if not scenario: raise HTTPException(404, '故障剧本不存在')
    pending = db.scalars(select(TxDrill.id).where(TxDrill.status.in_(['queued','running']))).all()
    if len(pending) >= 20: raise HTTPException(429, '队列配额20已满，请稍后重试')
    data = payload.model_dump()
    snapshot = {'nodes': list_nodes(db), 'scenario': record(scenario),
                'txn_id': data['txn_id'], 'prepared': data['prepared'], 'concurrent': data['concurrent'],
                'verdict': data['verdict'], 'verdict_persisted': data['verdict_persisted'],
                'crash_after_verdict': data['crash_after_verdict'], 'redeliver': data['redeliver']}
    obj = TxDrill(scenario_id=scenario.id, label=payload.label, status='queued', snapshot=snapshot)
    db.add(obj); db.flush(); return obj

def list_tx_drills(db): return [record(d) for d in db.scalars(select(TxDrill).order_by(TxDrill.id.desc()).limit(100))]
def get_tx_drill(db, drill_id):
    obj = db.get(TxDrill, drill_id)
    if obj is None: raise HTTPException(404, '演练不存在')
    return obj
