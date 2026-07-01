from dataclasses import dataclass
from typing import Any, Callable, Optional

from midas.checker.environment import Environment
from midas.checker.registry import TypesRegistry
from midas.checker.types import (
    Function,
    GenericType,
    OverloadedFunction,
    TopType,
    Type,
    TypeVar,
    UnitType,
)


@dataclass(frozen=True)
class Param:
    name: str
    type: Type
    required: bool = True


class Preamble(Environment):
    def __init__(self, types: TypesRegistry) -> None:
        super().__init__()
        self._types: TypesRegistry = types
        self._python_funcs: dict[str, Callable[..., Any]] = {}

        self._def_type_constructor("object", object)
        self._def_type_constructor("float", float)
        self._def_type_constructor("int", int)
        self._def_type_constructor("bool", bool)
        self._def_type_constructor("str", str)
        self._def_function(
            name="list",
            pos=[Param("object", TopType())],
            returns=self._list_of(TopType()),
            py_function=list,
        )

        # TODO: use sink
        self._def_function(
            name="print",
            pos=[Param("object", TopType(), required=False)],
            returns=UnitType(),
            py_function=print,
        )

        map_in = TypeVar(name="T", bound=None)
        map_out = TypeVar(name="U", bound=None)
        mapper = self._make_function(
            name="MapTransform",
            pos=[Param("v", map_in)],
            returns=map_out,
        )
        self._def_function(
            name="map",
            pos=[
                Param("transform", mapper),
                Param(
                    "iterable",
                    self._list_of(map_in),  # TODO: replace with Iterable[T]
                ),
            ],
            returns=self._list_of(map_out),  # TODO: replace with Iterable[U]
            type_vars=[map_in, map_out],
            py_function=map,
        )
        self._def_function(
            name="input",
            pos=[Param("prompt", TopType(), required=False)],
            returns=self._types.get_type("str"),
        )
        self._def_function(
            name="len",
            pos=[Param("object", TopType())],
            returns=self._types.get_type("int"),
        )

        T = TypeVar(name="T", bound=None)
        self._def_overloads(
            name="max",
            py_function=max,
            signatures=[
                (
                    [Param("arg1", T), Param("arg2", T)],
                    [],
                    [],
                    T,
                    [T],
                ),
                ([Param("iterable", self._list_of(T))], [], [], T, [T]),
            ],
        )
        self._def_overloads(
            name="min",
            py_function=min,
            signatures=[
                (
                    [Param("arg1", T), Param("arg2", T)],
                    [],
                    [],
                    T,
                    [T],
                ),
                ([Param("iterable", self._list_of(T))], [], [], T, [T]),
            ],
        )

    def _list_of(self, item_type: Type) -> Type:
        return self._types.apply_generic(self._types.get_type("list"), [item_type])

    def _def_type_constructor(
        self, name: str, py_function: Optional[Callable[..., Any]] = None
    ):
        # TODO: more specific arg types
        self._def_function(
            name=name,
            pos=[Param("object", TopType(), required=False)],
            returns=self._types.get_type(name),
            py_function=py_function,
        )

    def _make_function(
        self,
        *,
        name: str,
        pos: list[Param] = [],
        mixed: list[Param] = [],
        kw: list[Param] = [],
        returns: Type = UnitType(),
        type_vars: list[TypeVar] = [],
    ) -> Type:
        def map_args(params: list[Param], offset: int) -> list[Function.Argument]:
            return [
                Function.Argument(
                    pos=i + offset,
                    name=param.name,
                    type=param.type,
                    required=param.required,
                )
                for i, param in enumerate(params)
            ]

        function = Function(
            pos_args=map_args(pos, 0),
            args=map_args(mixed, len(pos)),
            kw_args=map_args(kw, len(pos) + len(mixed)),
            returns=returns,
        )
        if len(type_vars) != 0:
            function = GenericType(
                name=name,
                params=type_vars,
                body=function,
            )
        return function

    def _def_function(
        self,
        *,
        name: str,
        pos: list[Param] = [],
        mixed: list[Param] = [],
        kw: list[Param] = [],
        returns: Type = UnitType(),
        type_vars: list[TypeVar] = [],
        py_function: Optional[Callable[..., Any]] = None,
    ):
        function: Type = self._make_function(
            name=name,
            pos=pos,
            mixed=mixed,
            kw=kw,
            returns=returns,
            type_vars=type_vars,
        )
        self.define(name, function)
        if py_function is not None:
            self._python_funcs[name] = py_function

    def _def_overloads(
        self,
        *,
        name: str,
        signatures: list[
            tuple[list[Param], list[Param], list[Param], Type, list[TypeVar]]
        ],
        py_function: Optional[Callable[..., Any]] = None,
    ):
        overloads: list[Type] = []
        for pos, mixed, kw, returns, type_vars in signatures:
            overloads.append(
                self._make_function(
                    name=name,
                    pos=pos,
                    mixed=mixed,
                    kw=kw,
                    returns=returns,
                    type_vars=type_vars,
                )
            )
        function: Type = OverloadedFunction(overloads=overloads)
        self.define(name, function)
        if py_function is not None:
            self._python_funcs[name] = py_function

    def get_py_func(self, name: str) -> Optional[Callable[..., Any]]:
        return self._python_funcs.get(name)
