from __future__ import annotations

from typing import TYPE_CHECKING

import midas.ast.python as p
from midas.ast.location import Location
from midas.checker.frames.column_groupby_methods import Call as GroupByCall
from midas.checker.frames.column_groupby_methods import ColumnGroupByMethodRegistry
from midas.checker.frames.column_methods import Call, ColumnMethodRegistry
from midas.checker.types import ColumnGroupBy, ColumnType, Type

if TYPE_CHECKING:
    from midas.checker.python import PythonTyper, TypedExpr


class ColumnManager:
    def __init__(self, typer: PythonTyper) -> None:
        self.typer: PythonTyper = typer
        self.method_resolver: ColumnMethodRegistry = ColumnMethodRegistry(self.typer)
        self.groupby_method_resolver: ColumnGroupByMethodRegistry = (
            ColumnGroupByMethodRegistry(self.typer)
        )

    def call(
        self,
        method: str,
        location: Location,
        call_expr: p.Expr,
        column: ColumnType,
        column_expr: p.Expr,
        positional: list[TypedExpr],
        keywords: dict[str, TypedExpr],
    ) -> Type:
        call: Call = Call(
            location=location,
            call_expr=call_expr,
            column=column,
            column_expr=column_expr,
            positional=positional,
            keywords=keywords,
        )
        return self.method_resolver.call(method, call)

    def groupby_call(
        self,
        method: str,
        location: Location,
        call_expr: p.Expr,
        groupby: ColumnGroupBy,
        groupby_expr: p.Expr,
        positional: list[TypedExpr],
        keywords: dict[str, TypedExpr],
    ) -> Type:
        call: GroupByCall = GroupByCall(
            location=location,
            call_expr=call_expr,
            groupby=groupby,
            groupby_expr=groupby_expr,
            positional=positional,
            keywords=keywords,
        )
        return self.groupby_method_resolver.call(method, call)
