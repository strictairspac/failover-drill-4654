import logging, time
from pathlib import Path
from sqlalchemy import select
from redis import Redis
from src.config.database import Session
from src.config.settings import REDIS_URL
from src.models.entities import Drill, TxDrill
from src.services.election import elect
from src.services.recovery import recover
redis = Redis.from_url(REDIS_URL)
logging.basicConfig(level=logging.INFO)
def claim(db, model):
    return db.scalar(select(model).where(model.status == 'queued').order_by(model.id).with_for_update(skip_locked=True))
def run(job, compute):
    job.status = 'running'
    try:
        job.result = compute(job.snapshot)
        job.status = 'completed'
    except ValueError as exc:
        job.result = {'error': str(exc), 'simulation': True}
        job.status = 'failed'
# Redis leadership lock ensures only one worker processes the durable DB queue.
while True:
    Path('/tmp/heartbeat').touch()
    lock = redis.lock('drill-worker', timeout=15, blocking_timeout=1)
    try:
        with lock:
            with Session() as db:
                job = claim(db, Drill)
                if job:
                    run(job, lambda snap: elect(snap['nodes'], snap['scenario']))
                    db.commit()
                    logging.info('drill %s %s', job.id, job.status)
                tx = claim(db, TxDrill)
                if tx:
                    run(tx, recover)
                    db.commit()
                    logging.info('tx-drill %s %s', tx.id, tx.status)
    except Exception:
        logging.exception('worker retry')
    time.sleep(1)
