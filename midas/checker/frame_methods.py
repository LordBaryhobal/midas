from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Optional

from midas.ast.location import Location
from midas.checker.registry import TypesRegistry
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
    from midas.checker.python import PythonTyper, TypedExpr


@staticmethod
def frame_method(*names: str):
    def wrapper(func):
        names_: tuple[str, ...] = names
        if len(names_) == 0:
            names_ = (func.__name__,)
        setattr(func, "__method_names__", names_)
        return func

    return wrapper


@dataclass(frozen=True, kw_only=True)
class Call:
    location: Location
    frame: DataFrameType
    positional: list[TypedExpr]
    keywords: dict[str, TypedExpr]


class _MethodRegistryMeta(type):
    _methods: dict[str, Callable] = {}

    def __new__(
        cls,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
    ):
        new_class = super().__new__(cls, name, bases, namespace)
        new_class._methods = {}
        for attr in namespace.values():
            if callable(attr) and hasattr(attr, "__method_names__"):
                for name in attr.__method_names__:  # type: ignore
                    new_class._methods[name] = attr
        return new_class


class MethodRegistry(metaclass=_MethodRegistryMeta):
    def __init__(self, typer: PythonTyper) -> None:
        self.typer: PythonTyper = typer

    @property
    def reporter(self) -> FileReporter:
        return self.typer.reporter

    @property
    def types(self) -> TypesRegistry:
        return self.typer.types

    def call(
        self,
        method: str,
        call: Call,
    ) -> Type:
        func: Optional[Callable] = self._methods.get(method)
        if func is None:
            self.reporter.error(call.location, f"Unknown method {method}")
            return UnknownType()
        return func(self, call)

    @frame_method("add", "__add__")
    def add(
        self,
        call: Call,
    ) -> Type:
        new_columns: list[DataFrameType.Column] = []

        by_name: dict[str, DataFrameType.Column] = {}
        frame2: Optional[DataFrameType] = None
        if len(call.positional) != 0:
            other: Type = call.positional[0][1]
            unfolded_other: Type = unfold_type(other)
            if isinstance(unfolded_other, DataFrameType):
                frame2 = unfolded_other
                by_name = {
                    col.name: col for col in frame2.columns if col.name is not None
                }

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
            self.typer._get_call_result(
                location=call.location,
                callee=signature,
                positional=call.positional,
                keywords=call.keywords,
            )
            or UnknownType()
        )
