from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Protocol

from midas.ast.location import Location
from midas.checker.reporter import FileReporter
from midas.checker.types import (
    ColumnType,
    DataFrameType,
    Function,
    Type,
    UnknownType,
    unfold_type,
)

if TYPE_CHECKING:
    from midas.checker.frames import FrameManager
    from midas.checker.python import PythonTyper, TypedExpr


class FrameMethod(Protocol):
    @property
    def __name__(self) -> str: ...
    def __call__(
        self,
        typer: PythonTyper,
        manager: FrameManager,
        reporter: FileReporter,
        location: Location,
        frame: DataFrameType,
        positional: list[TypedExpr],
        keywords: dict[str, TypedExpr],
    ) -> Type: ...


FRAME_METHODS: dict[str, FrameMethod] = {}


def frame_method(*names: str):
    def wrapper(func: FrameMethod):
        names_: tuple[str, ...] = names
        if len(names_) == 0:
            names_ = (func.__name__,)
        for name in names_:
            FRAME_METHODS[name] = func
        return func

    return wrapper


@frame_method("add", "__add__")
def add(
    typer: PythonTyper,
    manager: FrameManager,
    reporter: FileReporter,
    location: Location,
    frame: DataFrameType,
    positional: list[TypedExpr],
    keywords: dict[str, TypedExpr],
) -> Type:
    new_columns: list[DataFrameType.Column] = []

    by_name: dict[str, DataFrameType.Column] = {}
    frame2: Optional[DataFrameType] = None
    if len(positional) != 0:
        other: Type = positional[0][1]
        unfolded_other: Type = unfold_type(other)
        if isinstance(unfolded_other, DataFrameType):
            frame2 = unfolded_other
            by_name = {col.name: col for col in frame2.columns if col.name is not None}

    in_frame1: set[str] = set()
    for column in frame.columns:
        if column.name is not None:
            in_frame1.add(column.name)

        col_type1: Type = column.type
        col_type: Type = ColumnType(type=UnknownType())
        if column.name in by_name:
            column2 = by_name[column.name]
            col_type2: Type = column2.type
            if manager.types.are_equivalent(col_type2, col_type1):
                col_type = col_type1

        new_column = DataFrameType.Column(
            index=column.index,
            name=column.name,
            type=col_type,
        )
        new_columns.append(new_column)

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

    return (
        typer._get_call_result(
            location=location,
            callee=signature,
            positional=positional,
            keywords=keywords,
        )
        or UnknownType()
    )
