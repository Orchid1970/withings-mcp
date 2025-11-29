from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class WithingsObservation(BaseModel):
    """
    Pydantic schema describing a single observation returned from Withings.
    """
    measure_type: Literal["weight", "bmi", "heart_rate", "unknown"] = Field(
        ...,
        description="Canonical type of the measurement (e.g., weight, bmi, heart_rate).",
    )
    measure_label: str = Field(
        ...,
        description="Human-readable label for the measurement (e.g., 'Weight (lbs)').",
    )
    value: float = Field(
        ...,
        description="Numeric value of the measurement.",
    )
    unit: Optional[str] = Field(
        default=None,
        description="Unit associated with the measurement (e.g., 'lbs', 'kg', 'bpm').",
    )
    captured_at: datetime = Field(
        ...,
        description="Timestamp indicating when the measurement was recorded.",
    )
