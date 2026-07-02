from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Generic,
    Optional,
    Protocol,
    Self,
    TypeVar,
)

import midas.ast.python as p
from midas.ast.location import Location
from midas.checker.dispatcher import CallDispatcher
from midas.checker.registry import TypesRegistry
from midas.checker.reporter import FileReporter
from midas.checker.types import Type, UnknownType
from midas.generator.collector import AssertionCollector

if TYPE_CHECKING:
    from midas.checker.python import PythonTyper


@staticmethod
def method(*names: str):
    def wrapper(func):
        names_: tuple[str, ...] = names
        if len(names_) == 0:
            names_ = (func.__name__,)
        setattr(func, "__method_names__", names_)
        return func

    return wrapper


class _MethodRegistryMeta(type):
    _methods: dict[str, Callable[..., Type]] = {}

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
                    new_class._methods[name] = attr  # type: ignore
        return new_class


class HasLocation(Protocol):
    @property
    def location(self) -> Location: ...


T = TypeVar("T", bound=HasLocation)


class MethodRegistry(Generic[T], metaclass=_MethodRegistryMeta):
    def __init__(self, typer: PythonTyper) -> None:
        self.typer: PythonTyper = typer

    @property
    def reporter(self) -> FileReporter:
        return self.typer.reporter

    @property
    def types(self) -> TypesRegistry:
        return self.typer.types

    @property
    def dispatcher(self) -> CallDispatcher[p.Expr]:
        return self.typer.dispatcher

    @property
    def assertions(self) -> AssertionCollector:
        return self.typer.assertions

    def call(self, method: str, call: T) -> Type:
        func: Optional[Callable[[Self, T], Type]] = self._methods.get(method)
        if func is None:
            self.reporter.warning(call.location, f"Unknown method {method}")
            return UnknownType()
        return func(self, call)
