from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class InspectionContext:
    operator_id: Optional[str]
    field_name: Optional[str]
    well_name: Optional[str]
    date_start: Optional[date]
    date_end: Optional[date]
