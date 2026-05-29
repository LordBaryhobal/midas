# type: ignore
# ruff: disable[F821]
from __future__ import annotations

df: Frame[
    verified: bool,
    birth_year: int,
    height: float + ( _ > 0 ) + ( _ < 250 ),
    name: str,
    date: datetime,
    float,
    unknown: _,
    _
]
