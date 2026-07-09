# type: ignore
# ruff: disable[F821]
from __future__ import annotations


def func(
    col1: Column[float],
    col2: Column[float],
) -> Column[float]:
    return col1 + col2


def func2(a: int, /, b: float, *, c: str):
    pass
