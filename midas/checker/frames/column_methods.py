from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import midas.ast.python as p
from midas.ast.location import Location
from midas.checker.frames.utils import MethodRegistry
from midas.checker.types import (
    ColumnType,
)

if TYPE_CHECKING:
    from midas.checker.python import TypedExpr


@dataclass(frozen=True, kw_only=True)
class Call:
    location: Location
    call_expr: p.Expr
    column: ColumnType
    column_expr: p.Expr
    positional: list[TypedExpr]
    keywords: dict[str, TypedExpr]


class ColumnMethodRegistry(MethodRegistry[Call]): ...
