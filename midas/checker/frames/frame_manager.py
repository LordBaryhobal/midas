from __future__ import annotations

from typing import TYPE_CHECKING, Optional, TypeGuard, cast

import midas.ast.python as p
from midas.ast.location import Location
from midas.checker.frames.frame_groupby_methods import Call as GroupByCall
from midas.checker.frames.frame_groupby_methods import FrameGroupByMethodRegistry
from midas.checker.frames.frame_methods import Call, FrameMethodRegistry
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
    return all(isinstance(expr, p.LiteralExpr) for expr in exprs)


class FrameManager:
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
        if not isinstance(type, ColumnType):
            reporter.error(
                location,
                f"Cannot assign {type} to dataframe column. Must be a ColumnType",
            )
            return frame
        return self._set_column(frame, name, type)

    def get(
        self,
        reporter: FileReporter,
        location: Location,
        frame: DataFrameType,
        index: p.Expr,
    ) -> Type:
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
        for name, col in zip(names, columns):
            frame = cls._set_column(frame, name, col)
        return frame

    @classmethod
    def _get_column(cls, frame: DataFrameType, name: str) -> Optional[ColumnType]:
        for col in frame.columns:
            if col.name == name:
                return col.type
        return None

    @classmethod
    def _get_columns(
        cls, frame: DataFrameType, names: list[str]
    ) -> list[Optional[ColumnType]]:
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
        call: GroupByCall = GroupByCall(
            location=location,
            call_expr=call_expr,
            groupby=groupby,
            groupby_expr=groupby_expr,
            positional=positional,
            keywords=keywords,
        )
        return self.groupby_method_resolver.call(method, call)
