from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


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
        pos: int
        name: str
        type: Type
        required: bool


@dataclass(frozen=True, kw_only=True)
class ComplexType:
    properties: dict[str, Type]


@dataclass(frozen=True, kw_only=True)
class Operation:
    signature: CallSignature
    result: Type

    @dataclass(frozen=True, kw_only=True)
    class CallSignature:
        left: Type
        method: str
        right: Type


@dataclass(frozen=True, kw_only=True)
class TypeVar:
    name: str
    bound: Optional[Type]


@dataclass(frozen=True, kw_only=True)
class GenericType:
    params: list[TypeVar]
    body: Type


def substitute_typevars(type: Type, substitutions: dict[str, Type]) -> Type:
    def sub_argument(arg: Function.Argument):
        return Function.Argument(
            pos=arg.pos,
            name=arg.name,
            type=substitute_typevars(arg.type, substitutions),
            required=arg.required,
        )

    match type:
        case BaseType(name=name) if name in substitutions:
            return substitutions[name]

        case AliasType(name=name, type=type2):
            return AliasType(name=name, type=substitute_typevars(type2, substitutions))

        case Function(
            name=name,
            pos_args=pos_args,
            args=args,
            kw_args=kw_args,
            returns=returns,
        ):
            return Function(
                name=name,
                pos_args=list(map(sub_argument, pos_args)),
                args=list(map(sub_argument, args)),
                kw_args=list(map(sub_argument, kw_args)),
                returns=substitute_typevars(returns, substitutions),
            )

        case ComplexType(properties=properties):
            properties2: dict[str, Type] = {
                name: substitute_typevars(prop, substitutions)
                for name, prop in properties.items()
            }
            return ComplexType(properties=properties2)

        case TypeVar(name=name):
            if name in substitutions:
                return substitutions[name]
            raise ValueError(f"Missing TypeVar substitution for {name}")

        case UnknownType() | UnitType():
            return type

        case _:
            raise NotImplementedError(f"Unsupported type {type}")


Type = (
    BaseType
    | AliasType
    | UnknownType
    | UnitType
    | Function
    | ComplexType
    | TypeVar
    | GenericType
)
