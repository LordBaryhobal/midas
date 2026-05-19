# type: ignore
# ruff: disable[F821]
from __future__ import annotations

# A simple data-frame with different column of various simple types
# Columns can be named and/or typed
df: Frame[
    verified: bool,
    birth_year: int,
    height: float + ( _ > 0 ) + ( _ < 250 ),
    name: str,
    date: datetime,
    float,  # unnamed
    unknown: _,  # untyped
    _  # unnamed and untyped
]
