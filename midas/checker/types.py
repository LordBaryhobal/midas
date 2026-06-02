from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class BaseType:
    name: str


@dataclass(frozen=True, kw_only=True)
class AliasType:
    name: str
    type: Type


@dataclass(frozen=True, kw_only=True)
class UnknownType:
    pass


@dataclass(frozen=True, kw_only=True)
class UnitType:
    pass


@dataclass(frozen=True, kw_only=True)
class Function:
    name: str
    pos_args: list[Argument]
    args: list[Argument]
    kw_args: list[Argument]
    returns: Type

    @dataclass(frozen=True, kw_only=True)
    class Argument:
        name: str
        type: Type
        required: bool


@dataclass(frozen=True, kw_only=True)
class ComplexType:
    properties: dict[str, Type]


Type = BaseType | AliasType | UnknownType | UnitType | Function | ComplexType
