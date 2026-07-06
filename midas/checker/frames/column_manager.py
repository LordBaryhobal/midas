from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import midas.ast.python as p
from midas.ast.location import Location
from midas.checker.dispatcher import CallResult
from midas.checker.frames.column_groupby_methods import Call as GroupByCall
from midas.checker.frames.column_groupby_methods import ColumnGroupByMethodRegistry
from midas.checker.frames.column_methods import Call, ColumnMethodRegistry
from midas.checker.registry import TypesRegistry
from midas.checker.reporter import FileReporter
from midas.checker.types import (
    ColumnGroupBy,
    ColumnType,
    Function,
    OverloadedFunction,
    ParamSpec,
    Type,
)

if TYPE_CHECKING:
    from midas.checker.python import PythonTyper, TypedExpr


class ColumnManager:
    """Helper class to handle methods and subscripts on column types"""

    def __init__(self, typer: PythonTyper) -> None:
        self.typer: PythonTyper = typer
        self.method_resolver: ColumnMethodRegistry = ColumnMethodRegistry(self.typer)
        self.groupby_method_resolver: ColumnGroupByMethodRegistry = (
            ColumnGroupByMethodRegistry(self.typer)
        )

    def get(
        self,
        reporter: FileReporter,
        location: Location,
        column: ColumnType,
        index: TypedExpr,
    ) -> Type:
        """Compute the type of a subscript access

        Args:
            reporter (FileReporter): the file reporter to use for diagnostics
            location (Location): the subscript's location
            column (DataFrameType): the column type
            index (TypedExpr): the index

        Returns:
            Type: the resulting type
        """

        single = Function(
            params=ParamSpec(
                pos=[
                    Function.Parameter(
                        pos=0,
                        name="index",
                        type=self.typer.types.get_type("int"),
                        required=True,
                    )
                ]
            ),
            returns=column.type,
        )
        slice = Function(
            params=ParamSpec(
                pos=[
                    Function.Parameter(
                        pos=0,
                        name="slice",
                        type=self.typer.types.get_type("slice"),
                        required=True,
                    )
                ]
            ),
            returns=column,
        )

        overload = OverloadedFunction(overloads=[single, slice])

        result: CallResult = self.typer.dispatcher.get_result(
            location=location,
            callee=overload,
            positional=[index],
            keywords={},
        )
        return result.result

    def call(
        self,
        method: str,
        location: Location,
        call_expr: p.Expr,
        column: ColumnType,
        column_expr: p.Expr,
        positional: list[TypedExpr],
        keywords: dict[str, TypedExpr],
    ) -> Type:
        """Compute the result type of a column's method call

        Args:
            method (str): the method name
            location (Location): the call's location
            call_expr (p.Expr): the call expression
            column (ColumnType): the column type
            column_expr (p.Expr): the column expression
            positional (list[TypedExpr]): the list of positional arguments
            keywords (dict[str, TypedExpr]): the map of keyword arguments

        Returns:
            Type: the result type
        """
        call: Call = Call(
            location=location,
            call_expr=call_expr,
            column=column,
            column_expr=column_expr,
            positional=positional,
            keywords=keywords,
        )
        return self.method_resolver.call(method, call)

    def groupby_call(
        self,
        method: str,
        location: Location,
        call_expr: p.Expr,
        groupby: ColumnGroupBy,
        groupby_expr: p.Expr,
        positional: list[TypedExpr],
        keywords: dict[str, TypedExpr],
    ) -> Type:
        """Compute the result type of a column group-by's method call

        Args:
            method (str): the method name
            location (Location): the call's location
            call_expr (p.Expr): the call expression
            groupby (ColumnGroupBy): the column group-by object
            groupby_expr (p.Expr): the column group-by expression
            positional (list[TypedExpr]): the list of positional arguments
            keywords (dict[str, TypedExpr]): the map of keyword arguments

        Returns:
            Type: the result type
        """
        call: GroupByCall = GroupByCall(
            location=location,
            call_expr=call_expr,
            groupby=groupby,
            groupby_expr=groupby_expr,
            positional=positional,
            keywords=keywords,
        )
        return self.groupby_method_resolver.call(method, call)

    def get_attribute(self, column: ColumnType, name: str) -> Optional[Type]:
        """Get the type of a column's attribute

        Args:
            column (ColumnType): the column type
            name (str): the attribute's name

        Returns:
            Optional[Type]: the attribute's type, or `None` if it doesn't exist
        """
        types: TypesRegistry = self.typer.types
        match name:
            case "ndim" | "size":
                return types.get_type("int")

            case "shape":
                return types.tuple_of("int")

            case "T":
                return column

            case _:
                return None
