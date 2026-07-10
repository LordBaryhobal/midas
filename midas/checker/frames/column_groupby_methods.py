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
    Type,
    UnknownType,
)

if TYPE_CHECKING:
    from midas.checker.python import TypedExpr


@dataclass(frozen=True, kw_only=True)
class Call:
    """A column group-by method call, implements :class:`utils.MethodCall`"""

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
    """The method registry for column group-by types"""

    NAMED_ARGS: dict[str, str] = {
        "numeric_only": "bool",
        "skipna": "bool",
        "engine": "str",
        "engine_kwargs": "dict",
    }

    def _aggregate(
        self,
        call: Call,
        method: str,
        params: list[str | tuple[str, str, bool]] = [],
    ) -> Type:
        """Compute the result type of an aggregate method call

        Args:
            call (Call): the call object
            method (str): the method name to delegate on :class:`Column`
            params (list[str | tuple[str, str, bool], optional): a list of extra
                mixed parameters. The list can contain strings to include
                parameters predefined in `NAMED_ARGS`, or tuples containing the
                parameter's name, type and required flag. Defaults to [].

        Returns:
            Type: the result type
        """
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

        # TODO: maybe better to filter arguments and pass some, in case the
        # return type depends on them

        # Don't catch UndefinedMethodException because all aggregation
        # methods should be defined on columns too
        returns: Type = self.typer.call_method(
            location=call.location,
            call_expr=call.call_expr,
            obj=(call.groupby_expr, call.groupby.column),
            method_name=method,
            positional=[],
            keywords={},
        )
        if not isinstance(returns, ColumnType):
            returns = ColumnType(type=UnknownType())
        signature = Function(
            params=ParamSpec(mixed=real_params),
            returns=returns,
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
            "kurt",
            ["skipna", "numeric_only"],
        )

    @method()
    def max(self, call: Call) -> Type:
        return self._aggregate(
            call,
            "max",
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
            "mean",
            ["numeric_only", "skipna", "engine", "engine_kwargs"],
        )

    @method()
    def median(self, call: Call) -> Type:
        return self._aggregate(
            call,
            "median",
            ["numeric_only", "skipna"],
        )

    @method()
    def min(self, call: Call) -> Type:
        return self._aggregate(
            call,
            "min",
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
            "prod",
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
            "std",
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
            "sum",
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
            "var",
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
