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
    @method()
    def mean(self, call: Call) -> Type:
        bool_ = self.types.get_type("bool")
        signature = Function(
            args=[
                Function.Argument(
                    pos=0,
                    name="numeric_only",
                    type=bool_,
                    required=False,
                ),
                Function.Argument(
                    pos=1,
                    name="skipna",
                    type=bool_,
                    required=False,
                ),
                Function.Argument(
                    pos=2,
                    name="engine",
                    type=self.types.get_type("str"),
                    required=False,
                ),
                Function.Argument(
                    pos=3,
                    name="engine_kwargs",
                    type=self.types.get_type("dict"),
                    required=False,
                ),
            ],
            returns=call.groupby.frame,
        )

        result: CallResult = self.dispatcher.get_result(
            location=call.location,
            callee=signature,
            positional=call.positional,
            keywords=call.keywords,
        )
        return result.result
