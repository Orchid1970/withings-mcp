from datetime import datetime
from pydantic import BaseModel

class WithingsObservation(BaseModel):
    measure_type: str
    value: float
    unit: str | None = None
    captured_at: datetime
