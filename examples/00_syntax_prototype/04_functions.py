# type: ignore
# ruff: disable[F821]
from __future__ import annotations


def func(
    col1: Column[float + (0 <= _ <= 1)],
    col2: Column[float + (0 <= _ <= 1)],
) -> Column[float + (0 <= _ <= 2)]:
    result: Column[float + (0 <= _ <= 2)] = col1 + col2
    return result


def func2(a: int, /, b: float, *, c: str):
    pass
