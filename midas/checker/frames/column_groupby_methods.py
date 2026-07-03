from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import midas.ast.python as p
from midas.ast.location import Location
from midas.checker.dispatcher import CallResult
from midas.checker.frames.utils import MethodRegistry, method
from midas.checker.types import (
    ColumnGroupBy,
    ColumnType,
    Function,
    ParamSpec,
    TopType,
    Type,
)

if TYPE_CHECKING:
    from midas.checker.python import TypedExpr


@dataclass(frozen=True, kw_only=True)
class Call:
    location: Location
    call_expr: p.Expr
    groupby: ColumnGroupBy
    groupby_expr: p.Expr
    positional: list[TypedExpr]
    keywords: dict[str, TypedExpr]

    @property
    def subject(self) -> TypedExpr:
        return (self.groupby_expr, self.groupby)


class ColumnGroupByMethodRegistry(MethodRegistry[Call]):
    NAMED_ARGS: dict[str, str] = {
        "numeric_only": "bool",
        "skipna": "bool",
        "engine": "str",
        "engine_kwargs": "dict",
    }

    def _aggregate(
        self,
        call: Call,
        params: list[str | tuple[str, str, bool]] = [],
        *,
        preserve_inner_type: bool = False,
    ) -> Type:
        real_params: list[Function.Parameter] = []
        for i, param in enumerate(params):
            match param:
                case str() as name:
                    param = Function.Parameter(
                        pos=i,
                        name=name,
                        type=self.types.get_type(self.NAMED_ARGS[name]),
                        required=False,
                    )
                case (name, type, required):
                    param = Function.Parameter(
                        pos=i,
                        name=name,
                        type=self.types.get_type(type),
                        required=required,
                    )
            real_params.append(param)

        signature = Function(
            params=ParamSpec(mixed=real_params),
            returns=(
                call.groupby.column
                if preserve_inner_type
                else ColumnType(type=TopType())
            ),
        )

        result: CallResult = self.dispatcher.get_result(
            location=call.location,
            callee=signature,
            positional=call.positional,
            keywords=call.keywords,
        )
        return result.result

    @method()
    def kurt(self, call: Call) -> Type:
        return self._aggregate(
            call,
            ["skipna", "numeric_only"],
        )

    @method()
    def max(self, call: Call) -> Type:
        return self._aggregate(
            call,
            [
                "numeric_only",
                (
                    "min_count",
                    "int",
                    False,
                ),
                "skipna",
                "engine",
                "engine_kwargs",
            ],
            preserve_inner_type=True,
        )

    @method()
    def mean(self, call: Call) -> Type:
        return self._aggregate(
            call,
            ["numeric_only", "skipna", "engine", "engine_kwargs"],
        )

    @method()
    def median(self, call: Call) -> Type:
        return self._aggregate(
            call,
            ["numeric_only", "skipna"],
            preserve_inner_type=True,
        )

    @method()
    def min(self, call: Call) -> Type:
        return self._aggregate(
            call,
            [
                "numeric_only",
                (
                    "min_count",
                    "int",
                    False,
                ),
                "skipna",
                "engine",
                "engine_kwargs",
            ],
            preserve_inner_type=True,
        )

    @method()
    def prod(self, call: Call) -> Type:
        return self._aggregate(
            call,
            [
                "numeric_only",
                (
                    "min_count",
                    "int",
                    False,
                ),
                "skipna",
            ],
        )

    @method()
    def std(self, call: Call) -> Type:
        return self._aggregate(
            call,
            [
                (
                    "ddof",
                    "int",
                    False,
                ),
                "engine",
                "engine_kwargs",
                "numeric_only",
                "skipna",
            ],
        )

    @method()
    def sum(self, call: Call) -> Type:
        return self._aggregate(
            call,
            [
                "numeric_only",
                (
                    "min_count",
                    "int",
                    False,
                ),
                "skipna",
                "engine",
                "engine_kwargs",
            ],
        )

    @method()
    def var(self, call: Call) -> Type:
        return self._aggregate(
            call,
            [
                (
                    "var",
                    "int",
                    False,
                ),
                "engine",
                "engine_kwargs",
                "numeric_only",
                "skipna",
            ],
        )
