from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True, kw_only=True)
class BaseType:
    name: str

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True, kw_only=True)
class AliasType:
    name: str
    type: Type

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True, kw_only=True)
class UnknownType:
    def __str__(self) -> str:
        return "<Unknown>"


@dataclass(frozen=True, kw_only=True)
class UnitType:
    def __str__(self) -> str:
        return "None"


@dataclass(frozen=True, kw_only=True)
class Function:
    name: str
    pos_args: list[Argument]
    args: list[Argument]
    kw_args: list[Argument]
    returns: Type

    def __str__(self) -> str:
        args: list[str] = []
        if len(self.pos_args) != 0:
            args += list(map(str, self.pos_args))
            if len(self.args) + len(self.kw_args) != 0:
                args.append("/")

        if len(self.args) != 0:
            args += list(map(str, self.args))

        if len(self.kw_args) != 0:
            if len(args) != 0:
                args.append("*")
            args += list(map(str, self.kw_args))

        return f"{self.name}({', '.join(args)}) -> {self.returns}"

    @dataclass(frozen=True, kw_only=True)
    class Argument:
        pos: int
        name: str
        type: Type
        required: bool

        def __str__(self) -> str:
            opt: str = "" if self.required else "?"
            return f"{self.name}: {self.type}{opt}"


@dataclass(frozen=True, kw_only=True)
class ComplexType:
    properties: dict[str, Type]

    def __str__(self) -> str:
        props: list[str] = [f"{name}: {type}" for name, type in self.properties.items()]
        return f"{{{', '.join(props)}}}"


@dataclass(frozen=True, kw_only=True)
class Operation:
    signature: CallSignature
    result: Type

    def __str__(self) -> str:
        return f"{self.signature} -> {self.result}"

    @dataclass(frozen=True, kw_only=True)
    class CallSignature:
        left: Type
        method: str
        right: Type

        def __str__(self) -> str:
            return f"{self.method}({self.left}, {self.right})"


@dataclass(frozen=True, kw_only=True)
class TypeVar:
    name: str
    bound: Optional[Type]

    def __str__(self) -> str:
        if self.bound is not None:
            return f"{self.name} <: {self.bound}"
        return self.name


@dataclass(frozen=True, kw_only=True)
class GenericType:
    name: str
    params: list[TypeVar]
    body: Type

    def __str__(self) -> str:
        return f"{self.name}[{', '.join(map(str, self.params))}]"


@dataclass(frozen=True, kw_only=True)
class AppliedType:
    name: str
    args: list[Type]
    body: Type

    def __str__(self) -> str:
        return f"{self.name}[{', '.join(map(str, self.args))}]"


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


def unfold_type(type: Type) -> Type:
    match type:
        case AliasType(type=ref_type):
            return unfold_type(ref_type)
        case _:
            return type


Type = (
    BaseType
    | AliasType
    | UnknownType
    | UnitType
    | Function
    | ComplexType
    | TypeVar
    | GenericType
    | AppliedType
)
