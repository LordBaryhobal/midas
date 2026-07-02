from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Optional

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


class FrameMethodRegistry(MethodRegistry):
    def call(self, method: str, call: Call) -> Type:
        func: Optional[Callable[..., Type]] = self._methods.get(method)
        if func is None:
            self.reporter.warning(call.location, f"Unknown method {method}")
            return UnknownType()
        return func(self, call)

    @method("add", "__add__")
    def add(self, call: Call) -> Type:
        # TODO: support add with scalar, sequence, Series, dict
        # TODO: check operation exists on inner column types

        new_columns: list[DataFrameType.Column] = []

        by_name: dict[str, DataFrameType.Column] = {}
        frame2: Optional[DataFrameType] = None
        # Get map of operand's columns by name, if there is at least 1 operand, which is a dataframe
        if len(call.positional) != 0:
            other: Type = call.positional[0][1]
            unfolded_other: Type = unfold_type(other)
            if isinstance(unfolded_other, DataFrameType):
                frame2 = unfolded_other
                by_name = {
                    col.name: col for col in frame2.columns if col.name is not None
                }

        # Compute new schema:
        # Step 1: for all columns in frame1:
        #  - if present in frame2 with equivalent type -> add to schema as is
        #  - if not -> add to schema as unknown
        in_frame1: set[str] = set()
        for column in call.frame.columns:
            if column.name is not None:
                in_frame1.add(column.name)

            col_type1: Type = column.type
            col_type: Type = ColumnType(type=UnknownType())
            if column.name in by_name:
                column2 = by_name[column.name]
                col_type2: Type = column2.type
                if self.types.are_equivalent(col_type2, col_type1):
                    col_type = col_type1

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
            returns=DataFrameType(columns=new_columns),
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

    @method()
    def mean(self, call: Call) -> Type:
        with_axis = Function(
            kw_args=[
                Function.Argument(
                    pos=0,
                    name="axis",
                    type=self.types.get_type("int"),
                    required=False,
                )
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
                )
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
