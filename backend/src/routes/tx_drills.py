import json
from fastapi import APIRouter, Depends
from fastapi.responses import Response
from src.config.database import get_db
from src.middlewares.auth import current_user, writable
from src.schemas.tx_drill import TxDrillInput
from src.services.tx_drill_service import create_tx_drill, list_tx_drills, get_tx_drill
from src.utils.serialize import record
from src.controllers.actions import audit
router = APIRouter()
@router.get('/tx-drills')
def listing(db=Depends(get_db), user=Depends(current_user)): return list_tx_drills(db)
@router.post('/tx-drills', status_code=202)
def create(data: TxDrillInput, db=Depends(get_db), user=Depends(writable)):
    obj = create_tx_drill(db, data); audit(db, user, f'tx-drill:enqueue:{obj.id}'); db.commit()
    # DB is the durable queue; worker claims queued rows transactionally.
    return record(obj)
@router.get('/tx-drills/{drill_id}')
def detail(drill_id: int, db=Depends(get_db), user=Depends(current_user)): return record(get_tx_drill(db, drill_id))
@router.get('/tx-drills/{drill_id}/export')
def export(drill_id: int, db=Depends(get_db), user=Depends(current_user)):
    obj = get_tx_drill(db, drill_id)
    return Response(json.dumps(record(obj), ensure_ascii=False, indent=2), media_type='application/json', headers={'Content-Disposition': f'attachment; filename="tx-drill-{obj.id}.json"'})
