from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import midas.ast.python as p
from midas.ast.location import Location
from midas.checker.dispatcher import CallResult
from midas.checker.frames.utils import MethodRegistry, method
from midas.checker.types import FrameGroupBy, Function, Type

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

    def _aggregate(
        self, call: Call, args: list[str | tuple[str, str, bool]] = []
    ) -> Type:
        real_args: list[Function.Argument] = []
        for i, arg in enumerate(args):
            match arg:
                case str() as name:
                    arg = Function.Argument(
                        pos=i,
                        name=name,
                        type=self.types.get_type(self.NAMED_ARGS[name]),
                        required=False,
                    )
                case (name, type, required):
                    arg = Function.Argument(
                        pos=i,
                        name=name,
                        type=self.types.get_type(type),
                        required=required,
                    )
            real_args.append(arg)

        signature = Function(
            args=real_args,
            returns=call.groupby.frame,
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
            [
                "skipna",
                "numeric_only",
            ],
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
