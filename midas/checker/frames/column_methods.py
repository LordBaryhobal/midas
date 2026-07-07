from __future__ import annotations

import ast
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
    OverloadedFunction,
    ParamSpec,
    TopType,
    Type,
    UnitType,
    UnknownType,
    unfold_type,
)

if TYPE_CHECKING:
    from midas.checker.python import TypedExpr


@dataclass(frozen=True, kw_only=True)
class Call:
    """A column method call, implements :class:`utils.MethodCall`"""

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
    """The method registry for column types"""

    def _simple_call(self, call: Call, function: Type) -> Type:
        """Get the result of calling a simple method

        This function is a simple wrapper around :func:`dispatcher.CallDispatcher.get_result`
        Args:
            call (Call): the call that triggered this resolution
            function (Type): the function type

        Returns:
            Type: the return type
        """
        result: CallResult = self.dispatcher.get_result(
            location=call.location,
            callee=function,
            positional=call.positional,
            keywords=call.keywords,
        )
        return result.result

    def _element_binary_op(self, call: Call, method: str) -> Type:
        """Compute the result of an element-wise binary operation

        This function delegates to the inner types for computing the resulting
        type.

        Args:
            call (Call): the call that triggered this resolution
            method (str): the method name

        Returns:
            Type: the resulting type
        """
        if len(call.positional) == 0:
            return UnknownType()

        col_type1: Type = call.column.type
        operand: TypedExpr = call.positional[0]
        unfolded_operand: Type = unfold_type(operand[1])
        col_type2: Type

        # Operand is a column -> get the inner type
        if isinstance(unfolded_operand, ColumnType):
            col_type2 = unfolded_operand.type
        # Otherwise use the operand type itself
        else:
            col_type2 = operand[1]

        new_inner_type = self.typer.result_of_binary_op(
            location=call.location,
            expr=call.call_expr,
            left=(call.column_expr, col_type1),
            right=(operand[0], col_type2),
            method=method,
        )
        return ColumnType(type=new_inner_type)

    def _element_wise(self, call: Call, method: str) -> Type:
        """Compute the result of an element-wise method call

        If the call is valid, this method also generates an assertion to check
        that both operands have the same length at runtime

        Args:
            call (Call): the call object
            method (str): the method's name

        Returns:
            Type: the result type
        """

        # Build signature with new column type and generic operand
        signature = Function(
            params=ParamSpec(
                mixed=[
                    Function.Parameter(
                        pos=0,
                        name="other",
                        type=TopType(),
                        required=True,
                    ),
                ],
            ),
            returns=self._element_binary_op(call, method),
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

    @method()
    def copy(self, call: Call) -> Type:
        return self._simple_call(
            call,
            Function(
                params=ParamSpec(
                    mixed=[
                        Function.Parameter(
                            pos=0,
                            name="deep",
                            type=self.types.get_type("bool"),
                            required=False,
                        )
                    ]
                ),
                returns=call.column,
            ),
        )

    @method()
    def info(self, call: Call) -> Type:
        def make_overload(memory_usage: Type, required: bool = False) -> Type:
            return Function(
                params=ParamSpec(
                    mixed=[
                        Function.Parameter(
                            pos=0,
                            name="verbose",
                            type=self.types.get_type("bool"),
                            required=False,
                        ),
                        Function.Parameter(
                            pos=1,
                            name="buf",
                            type=TopType(),
                            required=False,
                        ),
                        Function.Parameter(
                            pos=2,
                            name="max_cols",
                            type=self.types.get_type("int"),
                            required=False,
                        ),
                        Function.Parameter(
                            pos=3,
                            name="memory_usage",
                            type=memory_usage,
                            required=required,
                        ),
                        Function.Parameter(
                            pos=4,
                            name="show_counts",
                            type=self.types.get_type("bool"),
                            required=False,
                        ),
                    ]
                ),
                returns=UnitType(),
            )

        return self._simple_call(
            call,
            OverloadedFunction(
                overloads=[
                    make_overload(self.types.get_type("bool"), False),
                    make_overload(self.types.get_type("str"), True),
                ],
            ),
        )

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

    def _aggregate(
        self,
        call: Call,
        kwargs: list[Function.Parameter] = [],
        *,
        preserve_inner_type: bool = False,
    ) -> Type:
        """Compute the result type of an aggregate method call

        Args:
            call (Call): the call object
            kwargs (list[Function.Parameter], optional): a list of extra
                keyword-only parameters. Defaults to [].
            preserve_inner_type (bool, optional): If `True`, the result type
                will preserve the column's inner type (e.g. for `min`/`max`),
                otherwise the inner type is widened to `TopType`. Defaults to False.

        Returns:
            Type: the result type
        """
        signature = Function(
            params=ParamSpec(
                kw=[
                    Function.Parameter(
                        pos=0,
                        name="axis",
                        type=TopType(),
                        required=False,
                    ),
                    *kwargs,
                ],
            ),
            returns=call.column if preserve_inner_type else ColumnType(type=TopType()),
        )

        result: CallResult = self.dispatcher.get_result(
            location=call.location,
            callee=signature,
            positional=call.positional,
            keywords=call.keywords,
        )
        return result.result

    @method("kurtosis", "kurt")
    def kurtosis(self, call: Call) -> Type:
        return self._aggregate(call)

    @method()
    def max(self, call: Call) -> Type:
        return self._aggregate(call, preserve_inner_type=True)

    @method()
    def mean(self, call: Call) -> Type:
        return self._aggregate(call)

    @method()
    def median(self, call: Call) -> Type:
        return self._aggregate(call, preserve_inner_type=True)

    @method()
    def min(self, call: Call) -> Type:
        return self._aggregate(call, preserve_inner_type=True)

    @method()
    def mode(self, call: Call) -> Type:
        return self._aggregate(call, preserve_inner_type=True)

    @method("product", "prod")
    def product(self, call: Call) -> Type:
        return self._aggregate(call)

    @method()
    def std(self, call: Call) -> Type:
        return self._aggregate(
            call,
            [
                Function.Parameter(
                    pos=1,
                    name="ddof",
                    type=self.types.get_type("int"),
                    required=False,
                )
            ],
        )

    @method()
    def sum(self, call: Call) -> Type:
        return self._aggregate(call)

    @method()
    def var(self, call: Call) -> Type:
        return self._aggregate(
            call,
            [
                Function.Parameter(
                    pos=1,
                    name="var",
                    type=self.types.get_type("int"),
                    required=False,
                )
            ],
        )

    @method()
    def head(self, call: Call) -> Type:
        signature = Function(
            params=ParamSpec(
                mixed=[
                    Function.Parameter(
                        pos=0,
                        name="n",
                        type=self.types.get_type("int"),
                        required=False,
                    ),
                ],
            ),
            returns=call.column,
        )

        result: CallResult = self.dispatcher.get_result(
            location=call.location,
            callee=signature,
            positional=call.positional,
            keywords=call.keywords,
        )
        return result.result

    @method()
    def tail(self, call: Call) -> Type:
        signature = Function(
            params=ParamSpec(
                mixed=[
                    Function.Parameter(
                        pos=0,
                        name="n",
                        type=self.types.get_type("int"),
                        required=False,
                    ),
                ],
            ),
            returns=call.column,
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
            params=ParamSpec(
                mixed=[
                    Function.Parameter(
                        pos=0,
                        name="by",
                        type=TopType(),
                        required=False,
                    ),
                    Function.Parameter(
                        pos=1,
                        name="level",
                        type=TopType(),
                        required=False,
                    ),
                ],
                kw=[
                    Function.Parameter(
                        pos=i + 2,
                        name=name,
                        type=bool_,
                        required=False,
                    )
                    for i, name in enumerate(
                        ["as_index", "sort", "group_keys", "observed", "dropna"]
                    )
                ],
            ),
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
        """Generate an assertion to check that two columns have the same length

        Args:
            call_expr (p.Expr): the call expression, to insert the assertion
                at the right place
            column1 (p.Expr): the first column expression
            column2 (p.Expr): the second column expression
        """
        func_name: str = "__midas_column_same_length__"

        # Efficiently compute length
        # https://stackoverflow.com/a/15943975/11109181
        def len_of_col(col: ast.expr) -> ast.expr:
            return ast.Call(
                func=ast.Name(id="len"),
                args=[
                    ast.Attribute(
                        value=col,
                        attr="index",
                    )
                ],
                keywords=[],
            )

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
                            left=len_of_col(ast.Name(id="column1")),
                            ops=[ast.Eq()],
                            comparators=[
                                len_of_col(ast.Name(id="column2")),
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
