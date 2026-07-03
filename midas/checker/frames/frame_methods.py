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
    TopType,
    Type,
    UnknownType,
    unfold_type,
)

if TYPE_CHECKING:
    from midas.checker.python import TypedExpr


@dataclass(frozen=True, kw_only=True)
class Call:
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

    def _element_binary_op(self, call: Call, method: str) -> DataFrameType:
        """Compute the result of an element-wise binary operation

        This function delegates to the matching columns for computing resulting
        types. Any column only present in one of the frames is forwarded as a
        generic `ColumnType(type=UnknownType())`. Columns only in the second
        frame are append at the end of the schema.

        Args:
            call (Call): the call that triggered this resolution
            method (str): the method name

        Returns:
            DataFrameType: the resulting frame type
        """
        new_columns: list[DataFrameType.Column] = []

        by_name: dict[str, DataFrameType.Column] = {}
        frame2: Optional[DataFrameType] = None
        # Get map of operand's columns by name, if there is at least 1 operand, which is a dataframe
        if len(call.positional) != 0:
            operand: TypedExpr = call.positional[0]
            unfolded_other: Type = unfold_type(operand[1])
            if isinstance(unfolded_other, DataFrameType):
                frame2 = unfolded_other
                by_name = {
                    col.name: col for col in frame2.columns if col.name is not None
                }

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
            if column.name in by_name:
                column2 = by_name[column.name]
                col_type2: ColumnType = column2.type

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

        return DataFrameType(columns=new_columns)

    def _element_wise(self, call: Call, method: str) -> Type:
        # TODO: support scalar, sequence, Series, dict operand
        # Build signature with new schema and generic operand
        signature = Function(
            args=[
                Function.Argument(
                    pos=0,
                    name="other",
                    type=DataFrameType(columns=[]),
                    required=True,
                ),
            ],
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
                call.call_expr, call.frame_expr, call.positional[0][0]
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

    def _aggregate(self, call: Call, kwargs: list[Function.Argument] = []) -> Type:
        with_axis = Function(
            kw_args=[
                Function.Argument(
                    pos=0,
                    name="axis",
                    type=self.types.get_type("int"),
                    required=False,
                ),
                *kwargs,
            ],
            returns=ColumnType(type=TopType()),
        )
        without_axis = Function(
            kw_args=[
                Function.Argument(
                    pos=0,
                    name="axis",
                    type=self.types.get_type("None"),
                    required=True,
                ),
                *kwargs,
            ],
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
                Function.Argument(
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
                Function.Argument(
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
            args=[
                Function.Argument(
                    pos=0,
                    name="n",
                    type=self.types.get_type("int"),
                    required=False,
                ),
            ],
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
            args=[
                Function.Argument(
                    pos=0,
                    name="n",
                    type=self.types.get_type("int"),
                    required=False,
                ),
            ],
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
        func_name: str = "__midas_frame_same_length__"
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
                            left=ast.Attribute(
                                value=ast.Name(id="frame1"),
                                attr="size",
                            ),
                            ops=[ast.Eq()],
                            comparators=[
                                ast.Attribute(
                                    value=ast.Name(id="frame2"),
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
            inputs=[frame1, frame2],
            builder=lambda f1, f2: ast.Call(
                func=ast.Name(id=func_name),
                args=[f1, f2],
                keywords=[],
            ),
            message="DataFrames must have the same length",
        )
