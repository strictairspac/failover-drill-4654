from pydantic import BaseModel, Field
from typing import Literal
class Write(BaseModel):
    shard: str = Field(min_length=1, max_length=40, pattern=r'^[a-zA-Z0-9_-]+$')
    record: str = Field(min_length=1, max_length=80)
    value: str = Field(min_length=1, max_length=80)
class ConcurrentWrite(Write):
    txn: str = Field(min_length=1, max_length=40)
class TxDrillInput(BaseModel):
    scenario_id: int = Field(gt=0)
    label: str = Field(min_length=2, max_length=120)
    txn_id: str = Field(min_length=2, max_length=40, pattern=r'^[a-zA-Z0-9_-]+$')
    prepared: list[Write] = Field(min_length=1, max_length=8)
    concurrent: list[ConcurrentWrite] = Field(max_length=12, default=[])
    verdict: Literal['commit', 'abort'] = 'commit'
    verdict_persisted: bool = True
    crash_after_verdict: bool = False
    redeliver: int = Field(ge=0, le=5, default=0)
