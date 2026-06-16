from dataclasses import dataclass

from midas.checker.environment import Environment
from midas.checker.registry import TypesRegistry
from midas.checker.types import Function, GenericType, TopType, Type, TypeVar, UnitType


@dataclass(frozen=True)
class Param:
    name: str
    type: Type
    required: bool = True


class Preamble(Environment):
    def __init__(self, types: TypesRegistry) -> None:
        super().__init__()
        self._types: TypesRegistry = types

        self._def_type_constructor("object")
        self._def_type_constructor("float")
        self._def_type_constructor("int")
        self._def_type_constructor("bool")
        self._def_type_constructor("str")
        self._def_function(
            name="list",
            pos=[Param("object", TopType())],
            returns=self._list_of(TopType()),
        )

        # TODO: use sink
        self._def_function(
            name="print",
            pos=[Param("object", TopType())],
            returns=UnitType(),
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
        )

    def _list_of(self, item_type: Type) -> Type:
        return self._types.apply_generic(self._types.get_type("list"), [item_type])

    def _def_type_constructor(self, name: str):
        # TODO: more specific arg types
        self._def_function(
            name=name,
            pos=[Param("object", TopType(), required=False)],
            returns=self._types.get_type(name),
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
