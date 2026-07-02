from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

import midas.ast.python as p
from midas.ast.location import Location
from midas.checker.dispatcher import CallResult
from midas.checker.frames.utils import MethodRegistry, method
from midas.checker.types import (
    ColumnGroupBy,
    ColumnType,
    Function,
    GenericType,
    TopType,
    Type,
    TypeVar,
    UnknownType,
    unfold_type,
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

    @property
    def subject(self) -> TypedExpr:
        return (self.column_expr, self.column)


class ColumnMethodRegistry(MethodRegistry[Call]):
    def _element_binary_op(self, call: Call, method: str) -> ColumnType:
        """Compute the result of an element-wise binary operation

        This function delegates to the inner types for computing the resulting
        type.

        Args:
            call (Call): the call that triggered this resolution
            method (str): the method name

        Returns:
            ColumnType: the resulting column type
        """
        column2: Optional[ColumnType] = None

        col_type1: Type = call.column.type
        new_column: Type = ColumnType(type=UnknownType())
        if len(call.positional) != 0:
            other: Type = call.positional[0][1]
            unfolded_other: Type = unfold_type(other)
            if isinstance(unfolded_other, ColumnType):
                column2 = unfolded_other
                col_type2: Type = column2.type

                new_inner_type = self.typer.result_of_binary_op(
                    location=call.location,
                    expr=call.call_expr,
                    left=(call.column_expr, col_type1),
                    right=(call.positional[0][0], col_type2),
                    method=method,
                )
                new_column = ColumnType(type=new_inner_type)
        return new_column

    def _element_wise(self, call: Call, method: str) -> Type:
        # TODO: support add with scalar

        # Build signature with new column type and generic operand
        param_type: TypeVar = TypeVar(name="T", bound=None)
        signature = GenericType(
            name="add",
            params=[param_type],
            body=Function(
                args=[
                    Function.Argument(
                        pos=0,
                        name="other",
                        type=ColumnType(type=param_type),
                        required=True,
                    ),
                ],
                returns=self._element_binary_op(call, method),
            ),
        )

        # Map arguments and compute result type
        result: CallResult = self.dispatcher.get_result(
            location=call.location,
            callee=signature,
            positional=call.positional,
            keywords=call.keywords,
        )
        if result.is_valid:
            self._assert_same_length(
                call.call_expr, call.column_expr, call.positional[0][0]
            )

        return result.result

    @method("add", "__add__")
    def add(self, call: Call) -> Type:
        return self._element_wise(call, "__add__")

    @method("sub", "__sub__")
    def sub(self, call: Call) -> Type:
        return self._element_wise(call, "__sub__")

    @method("mul", "__mul__")
    def mul(self, call: Call) -> Type:
        return self._element_wise(call, "__mul__")

    @method("div", "truediv", "__truediv__")
    def truediv(self, call: Call) -> Type:
        return self._element_wise(call, "__truediv__")

    @method("floordiv", "__floordiv__")
    def floordiv(self, call: Call) -> Type:
        return self._element_wise(call, "__floordiv__")

    @method("mod", "__mod__")
    def mod(self, call: Call) -> Type:
        return self._element_wise(call, "__mod__")

    @method("pow", "__pow__")
    def pow(self, call: Call) -> Type:
        return self._element_wise(call, "__pow__")

    @method("lt", "__lt__")
    def lt(self, call: Call) -> Type:
        return self._element_wise(call, "__lt__")

    @method("gt", "__gt__")
    def gt(self, call: Call) -> Type:
        return self._element_wise(call, "__gt__")

    @method("le", "__le__")
    def le(self, call: Call) -> Type:
        return self._element_wise(call, "__le__")

    @method("ge", "__ge__")
    def ge(self, call: Call) -> Type:
        return self._element_wise(call, "__ge__")

    @method("ne", "__ne__")
    def ne(self, call: Call) -> Type:
        return self._element_wise(call, "__ne__")

    @method("eq", "__eq__")
    def eq(self, call: Call) -> Type:
        return self._element_wise(call, "__eq__")

    @method()
    def mean(self, call: Call) -> Type:
        signature = Function(
            kw_args=[
                Function.Argument(
                    pos=0,
                    name="axis",
                    type=TopType(),
                    required=False,
                )
            ],
            returns=ColumnType(type=TopType()),
        )

        result: CallResult = self.dispatcher.get_result(
            location=call.location,
            callee=signature,
            positional=call.positional,
            keywords=call.keywords,
        )
        return result.result

    @method()
    def groupby(self, call: Call) -> Type:
        bool_: Type = self.types.get_type("bool")
        function: Function = Function(
            args=[
                Function.Argument(
                    pos=0,
                    name="by",
                    type=TopType(),
                    required=False,
                ),
                Function.Argument(
                    pos=1,
                    name="level",
                    type=TopType(),
                    required=False,
                ),
            ],
            kw_args=[
                Function.Argument(
                    pos=2,
                    name="as_index",
                    type=bool_,
                    required=False,
                ),
                Function.Argument(
                    pos=3,
                    name="sort",
                    type=bool_,
                    required=False,
                ),
                Function.Argument(
                    pos=4,
                    name="group_keys",
                    type=bool_,
                    required=False,
                ),
                Function.Argument(
                    pos=5,
                    name="observed",
                    type=bool_,
                    required=False,
                ),
                Function.Argument(
                    pos=6,
                    name="dropna",
                    type=bool_,
                    required=False,
                ),
            ],
            returns=ColumnGroupBy(column=call.column),
        )

        result: CallResult = self.dispatcher.get_result(
            location=call.location,
            callee=function,
            positional=call.positional,
            keywords=call.keywords,
        )
        return result.result

    def _assert_same_length(self, call_expr: p.Expr, column1: p.Expr, column2: p.Expr):
        func_name: str = "__midas_column_same_length__"
        self.assertions.define(
            func_name,
            ast.FunctionDef(
                name=func_name,
                args=ast.arguments(
                    posonlyargs=[],
                    args=[
                        ast.arg(arg="column1"),
                        ast.arg(arg="column2"),
                    ],
                    kwonlyargs=[],
                    defaults=[],
                    kw_defaults=[],
                ),
                body=[
                    ast.Return(
                        value=ast.Compare(
                            left=ast.Attribute(
                                value=ast.Name(id="column1"),
                                attr="size",
                            ),
                            ops=[ast.Eq()],
                            comparators=[
                                ast.Attribute(
                                    value=ast.Name(id="column2"),
                                    attr="size",
                                )
                            ],
                        )
                    )
                ],
                decorator_list=[],
            ),
        )
        self.assertions.add(
            bound_expr=call_expr,
            inputs=[column1, column2],
            builder=lambda c1, c2: ast.Call(
                func=ast.Name(id=func_name),
                args=[c1, c2],
                keywords=[],
            ),
            message="Columns must have the same length",
        )
