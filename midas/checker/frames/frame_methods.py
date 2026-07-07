from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

import midas.ast.python as p
from midas.ast.location import Location
from midas.checker.dispatcher import CallResult
from midas.checker.frames.utils import MethodRegistry, method
from midas.checker.types import (
    ColumnType,
    DataFrameType,
    FrameGroupBy,
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
    """A frame method call, implements :class:`utils.MethodCall`"""

    location: Location
    call_expr: p.Expr
    frame: DataFrameType
    frame_expr: p.Expr
    positional: list[TypedExpr]
    keywords: dict[str, TypedExpr]

    @property
    def subject(self) -> TypedExpr:
        return (self.frame_expr, self.frame)


class FrameMethodRegistry(MethodRegistry[Call]):
    """The method registry for frame types"""

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

    def _get_method_result(
        self,
        call: Call,
        column1: ColumnType,
        column2: ColumnType,
        method: str,
    ) -> ColumnType:
        """Get the result of calling a method on a column, passing a second

        This function delegates to the main typer the resolution of the method
        member, as well as computing the result type. Because we don't have any
        AST expression for the individual columns, the frame expressions are
        used instead.

        Args:
            call (Call): the call that triggered this resolution
            column1 (ColumnType): the first column, i.e. left operand
            column2 (ColumnType): the second column, i.e. right operand
            method (str): the method name

        Returns:
            ColumnType: the resulting column.
                If the operation is invalid / doesn't exist,
                `ColumnType(type=UnknownType())` is returned
        """

        result: Type = self.typer.result_of_binary_op(
            location=call.location,
            expr=call.call_expr,
            left=(call.frame_expr, column1),
            right=(call.positional[0][0], column2),
            method=method,
        )

        if not isinstance(result, ColumnType):
            return ColumnType(type=UnknownType())
        return result

    def _element_binary_op(self, call: Call, method: str) -> tuple[Type, bool]:
        """Compute the result of an element-wise binary operation

        This function delegates to the matching columns for computing resulting
        types. Any column only present in one of the frames is forwarded as a
        generic `ColumnType(type=UnknownType())`. Columns only in the second
        frame are append at the end of the schema.

        Args:
            call (Call): the call that triggered this resolution
            method (str): the method name

        Returns:
            tuple[Type, bool]: the resulting type and a boolean indicating
                whether the operand is a frame
        """

        if len(call.positional) == 0:
            return UnknownType(), False

        operand: TypedExpr = call.positional[0]
        new_columns: list[DataFrameType.Column] = []

        by_name: dict[str, DataFrameType.Column] = {}
        frame2: Optional[DataFrameType] = None
        # Get map of operand's columns by name, if the operand is a dataframe
        unfolded_other: Type = unfold_type(operand[1])
        frame_operand: bool = isinstance(unfolded_other, DataFrameType)
        if frame_operand:
            frame2 = unfolded_other
            by_name = {col.name: col for col in frame2.columns if col.name is not None}

        # Compute new schema:
        # Step 1: for all columns in frame1:
        #  - if present in frame2 -> delegate operation to columns
        #  - if not -> add to schema as unknown
        in_frame1: set[str] = set()
        for column in call.frame.columns:
            if column.name is not None:
                in_frame1.add(column.name)

            col_type1: ColumnType = column.type
            col_type: ColumnType = ColumnType(type=UnknownType())

            col_type2: Optional[ColumnType] = None

            # Operand is a frame -> lookup column with the same name
            if frame2 is not None:
                if column.name in by_name:
                    column2 = by_name[column.name]
                    col_type2 = column2.type

            # Operand is not a frame -> scalar operation -> ad-hoc column
            else:
                col_type2 = ColumnType(type=operand[1])

            if col_type2 is not None:
                col_type = self._get_method_result(call, col_type1, col_type2, method)

            new_column = DataFrameType.Column(
                index=column.index,
                name=column.name,
                type=col_type,
            )
            new_columns.append(new_column)

        # Step 2: for all columns in frame2
        #  - if not in frame1 -> add to schema as unknown
        if frame2 is not None:
            for column in frame2.columns:
                if column.name in in_frame1:
                    continue
                new_columns.append(
                    DataFrameType.Column(
                        index=len(new_columns),
                        name=column.name,
                        type=ColumnType(type=UnknownType()),
                    )
                )

        return DataFrameType(columns=new_columns), frame_operand

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
        # TODO: support sequence, Series, dict operand
        returns, frame_operand = self._element_binary_op(call, method)

        # Build signature with new schema and generic operand
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
            returns=returns,
        )

        # Map arguments and compute result type
        result: CallResult = self.dispatcher.get_result(
            location=call.location,
            callee=signature,
            positional=call.positional,
            keywords=call.keywords,
        )
        if result.is_valid and frame_operand:
            self._assert_same_length(
                call.call_expr, call.frame_expr, call.positional[0][0]
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
                returns=call.frame,
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

    def _aggregate(self, call: Call, kwargs: list[Function.Parameter] = []) -> Type:
        """Compute the result type of an aggregate method call

        Args:
            call (Call): the call object
            kwargs (list[Function.Parameter], optional): a list of extra
                keyword-only parameters. Defaults to [].

        Returns:
            Type: the result type
        """
        with_axis = Function(
            params=ParamSpec(
                kw=[
                    Function.Parameter(
                        pos=0,
                        name="axis",
                        type=self.types.get_type("int"),
                        required=False,
                    ),
                    *kwargs,
                ],
            ),
            returns=ColumnType(type=TopType()),
        )
        without_axis = Function(
            params=ParamSpec(
                kw=[
                    Function.Parameter(
                        pos=0,
                        name="axis",
                        type=self.types.get_type("None"),
                        required=True,
                    ),
                    *kwargs,
                ],
            ),
            returns=TopType(),
        )
        overload = OverloadedFunction(
            overloads=[
                with_axis,
                without_axis,
            ]
        )

        result: CallResult = self.dispatcher.get_result(
            location=call.location,
            callee=overload,
            positional=call.positional,
            keywords=call.keywords,
        )
        return result.result

    @method("kurtosis", "kurt")
    def kurtosis(self, call: Call) -> Type:
        return self._aggregate(call)

    @method()
    def max(self, call: Call) -> Type:
        return self._aggregate(call)

    @method()
    def mean(self, call: Call) -> Type:
        return self._aggregate(call)

    @method()
    def median(self, call: Call) -> Type:
        return self._aggregate(call)

    @method()
    def min(self, call: Call) -> Type:
        return self._aggregate(call)

    @method()
    def mode(self, call: Call) -> Type:
        return self._aggregate(call)

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
            returns=call.frame,
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
            returns=call.frame,
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
            returns=FrameGroupBy(frame=call.frame),
        )

        result: CallResult = self.dispatcher.get_result(
            location=call.location,
            callee=function,
            positional=call.positional,
            keywords=call.keywords,
        )
        return result.result

    def _assert_same_length(self, call_expr: p.Expr, frame1: p.Expr, frame2: p.Expr):
        """Generate an assertion to check that two frames have the same length

        Args:
            call_expr (p.Expr): the call expression, to insert the assertion
                at the right place
            frame1 (p.Expr): the first frame expression
            frame2 (p.Expr): the second frame expression
        """
        func_name: str = "__midas_frame_same_length__"

        # Efficiently compute length
        # https://stackoverflow.com/a/15943975/11109181
        def len_of_df(df: ast.expr) -> ast.expr:
            return ast.Call(
                func=ast.Name(id="len"),
                args=[
                    ast.Attribute(
                        value=df,
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
                        ast.arg(arg="frame1"),
                        ast.arg(arg="frame2"),
                    ],
                    kwonlyargs=[],
                    defaults=[],
                    kw_defaults=[],
                ),
                body=[
                    ast.Return(
                        value=ast.Compare(
                            left=len_of_df(ast.Name(id="frame1")),
                            ops=[ast.Eq()],
                            comparators=[len_of_df(ast.Name(id="frame2"))],
                        )
                    )
                ],
                decorator_list=[],
            ),
        )
        self.assertions.add(
            bound_expr=call_expr,
            inputs=[frame1, frame2],
            builder=lambda f1, f2: ast.Call(
                func=ast.Name(id=func_name),
                args=[f1, f2],
                keywords=[],
            ),
            message="DataFrames must have the same length",
        )
