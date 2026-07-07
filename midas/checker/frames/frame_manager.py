from __future__ import annotations

from typing import TYPE_CHECKING, Optional, TypeGuard, cast

import midas.ast.python as p
from midas.ast.location import Location
from midas.checker.frames.frame_groupby_methods import Call as GroupByCall
from midas.checker.frames.frame_groupby_methods import FrameGroupByMethodRegistry
from midas.checker.frames.frame_methods import Call, FrameMethodRegistry
from midas.checker.registry import TypesRegistry
from midas.checker.reporter import FileReporter
from midas.checker.types import (
    ColumnGroupBy,
    ColumnType,
    DataFrameType,
    FrameGroupBy,
    TupleType,
    Type,
    UnknownType,
)

if TYPE_CHECKING:
    from midas.checker.python import PythonTyper, TypedExpr


def is_list_of_literals(exprs: list[p.Expr]) -> TypeGuard[list[p.LiteralExpr]]:
    """Check whether the given list only contains literal expressions

    Args:
        exprs (list[p.Expr]): the list to check

    Returns:
        TypeGuard[list[p.LiteralExpr]]: whether `exprs` only contains literal expressions
    """
    return all(isinstance(expr, p.LiteralExpr) for expr in exprs)


class FrameManager:
    """Helper class to handle methods and subscripts on frame types"""

    def __init__(self, typer: PythonTyper) -> None:
        self.typer: PythonTyper = typer
        self.method_resolver: FrameMethodRegistry = FrameMethodRegistry(self.typer)
        self.groupby_method_resolver: FrameGroupByMethodRegistry = (
            FrameGroupByMethodRegistry(self.typer)
        )

    def assign(
        self,
        reporter: FileReporter,
        location: Location,
        frame: DataFrameType,
        index: p.Expr,
        value_type: Type,
    ) -> Type:
        """Compute the new frame type after assigning a value to an index

        Args:
            reporter (FileReporter): the file reporter to use for diagnostics
            location (Location): the assignment's location
            frame (DataFrameType): the frame type
            index (p.Expr): the index expression
            value_type (Type): the assigned value

        Returns:
            Type: the resulting frame type
        """
        match index:
            case p.LiteralExpr(value=str() as name):
                return self.assign_column(reporter, location, frame, name, value_type)

            case p.ListExpr(items=indices) if is_list_of_literals(indices) and all(
                isinstance(index.value, str) for index in indices
            ):
                names: list[str] = [cast(str, index.value) for index in indices]

                if not isinstance(value_type, TupleType):
                    reporter.error(
                        location,
                        f"Cannot assign {type} to dataframe columns. Must be a tuple of columns",
                    )
                    return UnknownType()

                if len(names) != len(value_type.items):
                    reporter.error(
                        location,
                        f"Wrong number of columns. Cannot assign {len(value_type.items)} to {len(names)} targets",
                    )
                    return UnknownType()

                new_frame: Type = frame
                for name, value in zip(names, value_type.items):
                    new_frame = self.assign_column(
                        reporter,
                        location,
                        new_frame,
                        name,
                        value,
                    )
                    if not isinstance(new_frame, DataFrameType):
                        return new_frame
                return new_frame

            case _:
                reporter.error(
                    location, f"Invalid index type {index} on {frame} (assignment)"
                )
                return UnknownType()

    def assign_column(
        self,
        reporter: FileReporter,
        location: Location,
        frame: DataFrameType,
        name: str,
        type: Type,
    ) -> Type:
        """Compute the new frame type after assigning a single value to a column

        Args:
            reporter (FileReporter): the file reporter to use for diagnostics
            location (Location): the assignment's location
            frame (DataFrameType): the frame type
            name (str): the column name
            type (Type): the assigned value type

        Returns:
            Type: the resulting frame type
        """
        if not isinstance(type, ColumnType):
            reporter.error(
                location,
                f"Cannot assign {type} to dataframe column. Must be a ColumnType",
            )
            return self._set_column(frame, name, ColumnType(type=UnknownType()))
        return self._set_column(frame, name, type)

    def get(
        self,
        reporter: FileReporter,
        location: Location,
        frame: DataFrameType,
        index: p.Expr,
    ) -> Type:
        """Compute the type of a subscript access

        Args:
            reporter (FileReporter): the file reporter to use for diagnostics
            location (Location): the subscript's location
            frame (DataFrameType): the frame type
            index (p.Expr): the index expression

        Returns:
            Type: the resulting type
        """
        match index:
            case p.LiteralExpr(value=str() as name):
                column: Optional[ColumnType] = FrameManager._get_column(frame, name)
                if column is None:
                    reporter.error(location, f"Unknown column '{name}' on {frame}")
                    return UnknownType()
                return column

            case p.ListExpr(items=indices) if is_list_of_literals(indices) and all(
                isinstance(index.value, str) for index in indices
            ):
                names: list[str] = [cast(str, index.value) for index in indices]
                columns: list[ColumnType] = []
                for name in names:
                    column: Optional[ColumnType] = FrameManager._get_column(frame, name)
                    if column is None:
                        reporter.error(location, f"Unknown column '{name}' on {frame}")
                        return UnknownType()
                    columns.append(column)
                return TupleType(items=tuple(columns))

            case _:
                reporter.error(
                    location, f"Invalid index type {index} on {frame} (access)"
                )
                return UnknownType()

    def groupby_get(
        self,
        reporter: FileReporter,
        location: Location,
        groupby: FrameGroupBy,
        index: p.Expr,
    ) -> Type:
        """Compute the type of a subscript access on a frame group-by object

        Args:
            reporter (FileReporter): the file reporter to use for diagnostics
            location (Location): the subscript's location
            groupby (FrameGroupBy): the group-by object
            index (p.Expr): the index expression

        Returns:
            Type: the resulting type
        """
        result: Type = self.get(reporter, location, groupby.frame, index)
        match result:
            case ColumnType():
                result = ColumnGroupBy(column=result)
            case TupleType(items=columns):
                result = TupleType(
                    items=tuple(
                        ColumnGroupBy(column=cast(ColumnType, column))
                        for column in columns
                    )
                )
        return result

    @classmethod
    def _set_column(
        cls, frame: DataFrameType, name: str, column: ColumnType
    ) -> DataFrameType:
        """Set a frame's column to the given type

        Args:
            frame (DataFrameType): the frame type
            name (str): the column's name
            column (ColumnType): the new column's type

        Returns:
            DataFrameType: the new frame type
        """
        new_columns: list[DataFrameType.Column] = []
        index: int = len(frame.columns)
        replace: bool = False
        for i, col in enumerate(frame.columns):
            if col.name == name:
                index = i
                replace = True
                # TODO: check column type here to prevent changing it
            new_columns.append(col)

        new_col: DataFrameType.Column = DataFrameType.Column(
            index=index,
            name=name,
            type=column,
        )
        if replace:
            new_columns[index] = new_col
        else:
            new_columns.append(new_col)

        return DataFrameType(columns=new_columns)

    @classmethod
    def _set_columns(
        cls, frame: DataFrameType, names: list[str], columns: list[ColumnType]
    ) -> DataFrameType:
        """Set multiple columns of a frame to the given types

        Args:
            frame (DataFrameType): the frame type
            names (list[str]): the column names
            columns (list[ColumnType]): the new column types

        Returns:
            DataFrameType: the new frame type
        """
        for name, col in zip(names, columns):
            frame = cls._set_column(frame, name, col)
        return frame

    @classmethod
    def _get_column(cls, frame: DataFrameType, name: str) -> Optional[ColumnType]:
        """Get a column's type by name

        Args:
            frame (DataFrameType): the frame type
            name (str): the column's name

        Returns:
            Optional[ColumnType]: the column's type, or `None` if it doesn't exist
        """
        for col in frame.columns:
            if col.name == name:
                return col.type
        return None

    @classmethod
    def _get_columns(
        cls, frame: DataFrameType, names: list[str]
    ) -> list[Optional[ColumnType]]:
        """Get multiple column types by name

        Args:
            frame (DataFrameType): the frame type
            names (list[str]): the column names

        Returns:
            list[Optional[ColumnType]]: the column types (see :func:`_get_column`)
        """
        return [cls._get_column(frame, name) for name in names]

    def call(
        self,
        method: str,
        location: Location,
        call_expr: p.Expr,
        frame: DataFrameType,
        frame_expr: p.Expr,
        positional: list[TypedExpr],
        keywords: dict[str, TypedExpr],
    ) -> Type:
        """Compute the result type of a frame's method call

        Args:
            method (str): the method name
            location (Location): the call's location
            call_expr (p.Expr): the call expression
            frame (DataFrameType): the frame type
            frame_expr (p.Expr): the frame expression
            positional (list[TypedExpr]): the list of positional arguments
            keywords (dict[str, TypedExpr]): the map of keyword arguments

        Returns:
            Type: the result type
        """
        call: Call = Call(
            location=location,
            call_expr=call_expr,
            frame=frame,
            frame_expr=frame_expr,
            positional=positional,
            keywords=keywords,
        )
        return self.method_resolver.call(method, call)

    def groupby_call(
        self,
        method: str,
        location: Location,
        call_expr: p.Expr,
        groupby: FrameGroupBy,
        groupby_expr: p.Expr,
        positional: list[TypedExpr],
        keywords: dict[str, TypedExpr],
    ) -> Type:
        """Compute the result type of a frame group-by's method call

        Args:
            method (str): the method name
            location (Location): the call's location
            call_expr (p.Expr): the call expression
            groupby (FrameGroupBy): the frame group-by object
            groupby_expr (p.Expr): the frame group-by expression
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

    def get_attribute(self, frame: DataFrameType, name: str) -> Optional[Type]:
        """Get the type of a frame's attribute

        Args:
            frame (DataFrameType): the frame type
            name (str): the attribute's name

        Returns:
            Optional[Type]: the attribute's type, or `None` if it doesn't exist
        """
        types: TypesRegistry = self.typer.types
        match name:
            case "ndim" | "size":
                return types.get_type("int")

            case "shape":
                return types.tuple_of("int", "int")

            case _:
                return None
