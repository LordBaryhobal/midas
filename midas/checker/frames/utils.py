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
    from midas.checker.python import PythonTyper, TypedExpr


class _MethodRegistryMeta(type):
    """Meta-class for :class:`MethodRegistry`

    Collects methods marked with the :func:`method` decorator into a dictionary
    named `_methods` on the class itself
    """

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


class MethodCall(Protocol):
    """A method call object

    Must have at least `location`, `call_expr` and `subject` properties
    """

    @property
    def location(self) -> Location: ...

    @property
    def call_expr(self) -> p.Expr: ...

    @property
    def subject(self) -> TypedExpr: ...


T = TypeVar("T", bound=MethodCall)


class MethodRegistry(Generic[T], metaclass=_MethodRegistryMeta):
    """A registry of methods"""

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
        """Compute the result type of a call to the given method

        Args:
            method (str): the method's name
            call (T): the call

        Returns:
            Type: the result type
        """
        func: Optional[Callable[[Self, T], Type]] = self._methods.get(method)
        if func is None:
            self.reporter.warning(
                call.location, f"Unknown method {method} on {call.subject[1]}"
            )
            return UnknownType()
        return func(self, call)


_Self = TypeVar("_Self", bound=MethodRegistry[Any])
Method = Callable[[_Self, T], Type]


def method(*names: str) -> Callable[[Method[_Self, T]], Method[_Self, T]]:
    """Simple decorator to mark a method as part of the registry

    Args:
        names (str): names by which the method can be called. If left empty, the
            Python method's name will be used
    """

    def wrapper(func: Method[_Self, T]) -> Method[_Self, T]:
        names_: tuple[str, ...] = names
        if len(names_) == 0:
            names_ = (func.__name__,)
        setattr(func, "__method_names__", names_)
        return func

    return wrapper
