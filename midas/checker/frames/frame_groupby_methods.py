from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import midas.ast.python as p
from midas.ast.location import Location
from midas.checker.frames.utils import MethodRegistry, method
from midas.checker.types import (
    ColumnGroupBy,
    ColumnType,
    DataFrameType,
    FrameGroupBy,
    Type,
    UnknownType,
)

if TYPE_CHECKING:
    from midas.checker.python import TypedExpr


@dataclass(frozen=True, kw_only=True)
class Call:
    location: Location
    call_expr: p.Expr
    groupby: FrameGroupBy
    groupby_expr: p.Expr
    positional: list[TypedExpr]
    keywords: dict[str, TypedExpr]

    @property
    def subject(self) -> TypedExpr:
        return (self.groupby_expr, self.groupby)


class FrameGroupByMethodRegistry(MethodRegistry[Call]):
    NAMED_ARGS: dict[str, str] = {
        "numeric_only": "bool",
        "skipna": "bool",
        "engine": "str",
        "engine_kwargs": "dict",
    }

    def _aggregate(self, call: Call, method: str) -> Type:
        new_columns: list[DataFrameType.Column] = []

        for column in call.groupby.frame.columns:
            column_groupby: ColumnGroupBy = ColumnGroupBy(column=column.type)
            result_type: Type = self.typer.call_method(
                location=call.location,
                call_expr=call.call_expr,
                obj=(call.groupby_expr, column_groupby),
                method_name=method,
                positional=call.positional,
                keywords=call.keywords,
            )
            if not isinstance(result_type, ColumnType):
                result_type = ColumnType(type=UnknownType())
            new_columns.append(
                DataFrameType.Column(
                    index=column.index,
                    name=column.name,
                    type=result_type,
                )
            )

        return DataFrameType(columns=new_columns)

    @method()
    def kurt(self, call: Call) -> Type:
        return self._aggregate(call, "kurt")

    @method()
    def max(self, call: Call) -> Type:
        return self._aggregate(call, "max")

    @method()
    def mean(self, call: Call) -> Type:
        return self._aggregate(call, "mean")

    @method()
    def median(self, call: Call) -> Type:
        return self._aggregate(call, "median")

    @method()
    def min(self, call: Call) -> Type:
        return self._aggregate(call, "min")

    @method()
    def prod(self, call: Call) -> Type:
        return self._aggregate(call, "prod")

    @method()
    def std(self, call: Call) -> Type:
        return self._aggregate(call, "std")

    @method()
    def sum(self, call: Call) -> Type:
        return self._aggregate(call, "sum")

    @method()
    def var(self, call: Call) -> Type:
        return self._aggregate(call, "var")
