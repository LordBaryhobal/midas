from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Optional, assert_never, cast

import midas.ast.midas as m
from midas.ast.printer import MidasPrinter


@dataclass(frozen=True, kw_only=True)
class TopType:
    def __str__(self) -> str:
        return "Any"


@dataclass(frozen=True, kw_only=True)
class BaseType:
    name: str

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True, kw_only=True)
class DerivedType:
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
    pos_args: list[Argument] = field(default_factory=list)
    args: list[Argument] = field(default_factory=list)
    kw_args: list[Argument] = field(default_factory=list)
    returns: Type

    def __str__(self) -> str:
        args: list[str] = []
        if len(self.pos_args) != 0:
            args += list(map(str, self.pos_args))
            args.append("/")

        if len(self.args) != 0:
            args += list(map(str, self.args))

        if len(self.kw_args) != 0:
            args.append("*")
            args += list(map(str, self.kw_args))

        return f"({', '.join(args)}) -> {self.returns}"

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
class OverloadedFunction:
    overloads: list[Type]

    def __str__(self) -> str:
        return "<overloaded function>"


@dataclass(frozen=True, kw_only=True)
class ComplexType:
    members: dict[str, Type]

    def __str__(self) -> str:
        props: list[str] = [f"{name}: {type}" for name, type in self.members.items()]
        return f"{{{', '.join(props)}}}"


@dataclass(frozen=True, kw_only=True)
class ExtensionType:
    base: Type
    extension: ComplexType

    def __str__(self) -> str:
        return f"{self.base} & {self.extension}"


class Variance(StrEnum):
    INVARIANT = "INVARIANT"
    COVARIANT = "COVARIANT"
    CONTRAVARIANT = "CONTRAVARIANT"


@dataclass(frozen=True, kw_only=True)
class TypeVar:
    name: str
    bound: Optional[Type]
    variance: Variance = Variance.INVARIANT

    def __str__(self) -> str:
        variance: str = {
            Variance.COVARIANT: "+",
            Variance.CONTRAVARIANT: "-",
        }.get(self.variance, "")
        res: str = f"{variance}{self.name}"
        if self.bound is not None:
            res = f"{res} <: {self.bound}"
        return res


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


@dataclass(frozen=True, kw_only=True)
class ConstraintType:
    type: Type
    constraint: m.Expr

    def __str__(self) -> str:
        printer = MidasPrinter()
        return f"{self.type} where {printer.print(self.constraint)}"


@dataclass(frozen=True, kw_only=True)
class TupleType:
    items: tuple[Type, ...]

    def __str__(self) -> str:
        return f"({', '.join(map(str, self.items))})"


@dataclass(frozen=True, kw_only=True)
class ColumnType:
    type: Type

    def __str__(self) -> str:
        return f"Column[{self.type}]"


@dataclass(frozen=True, kw_only=True)
class DataFrameType:
    columns: list[Column]

    def __str__(self) -> str:
        schema: list[str] = [f"{col.name}: {col.type}" for col in self.columns]
        return f"Frame[{', '.join(schema)}]"

    @dataclass(frozen=True, kw_only=True)
    class Column:
        index: int
        name: Optional[str]
        type: ColumnType


@dataclass(frozen=True, kw_only=True)
class FrameGroupBy:
    frame: DataFrameType

    def __str__(self) -> str:
        return f"FrameGroupBy[{self.frame}]"


def substitute_typevars(type: Type, substitutions: dict[str, Type]) -> Type:
    def sub_argument(arg: Function.Argument):
        return Function.Argument(
            pos=arg.pos,
            name=arg.name,
            type=substitute_typevars(arg.type, substitutions),
            required=arg.required,
        )

    def sub_column(col: DataFrameType.Column):
        return DataFrameType.Column(
            index=col.index,
            name=col.name,
            type=cast(ColumnType, substitute_typevars(col.type, substitutions)),
        )

    match type:
        case TopType():
            return type

        case BaseType(name=name) if name in substitutions:
            return substitutions[name]

        case BaseType():
            return type

        case DerivedType(name=name, type=type2):
            return DerivedType(
                name=name, type=substitute_typevars(type2, substitutions)
            )

        case Function(
            pos_args=pos_args,
            args=args,
            kw_args=kw_args,
            returns=returns,
        ):
            return Function(
                pos_args=list(map(sub_argument, pos_args)),
                args=list(map(sub_argument, args)),
                kw_args=list(map(sub_argument, kw_args)),
                returns=substitute_typevars(returns, substitutions),
            )

        case OverloadedFunction(overloads=overloads):
            return OverloadedFunction(
                overloads=[
                    substitute_typevars(overload, substitutions)
                    for overload in overloads
                ]
            )

        case ComplexType(members=members):
            members2: dict[str, Type] = {
                name: substitute_typevars(prop, substitutions)
                for name, prop in members.items()
            }
            return ComplexType(members=members2)

        case ExtensionType(base=base, extension=ComplexType(members=members)):
            return ExtensionType(
                base=substitute_typevars(base, substitutions),
                extension=ComplexType(
                    members={
                        name: substitute_typevars(prop, substitutions)
                        for name, prop in members.items()
                    }
                ),
            )

        case AppliedType(name=name, args=args, body=body):
            return AppliedType(
                name=name,
                args=[substitute_typevars(arg, substitutions) for arg in args],
                body=substitute_typevars(body, substitutions),
            )

        case ConstraintType():
            return ConstraintType(
                type=substitute_typevars(type.type, substitutions),
                constraint=type.constraint,
            )

        case TypeVar(name=name):
            if name in substitutions:
                return substitutions[name]
            raise ValueError(f"Missing TypeVar substitution for {name}")

        case GenericType(name=name, params=params, body=body):
            params2: list[TypeVar] = []
            for param in params:
                param2: Type = substitute_typevars(param, substitutions)
                if not isinstance(param2, TypeVar):
                    raise ValueError(
                        f"Invalid type parameter substitution, expected TypeVar, got {param2}"
                    )
                params2.append(param2)
            return GenericType(
                name=name,
                params=params2,
                body=substitute_typevars(body, substitutions),
            )

        case TupleType(items=items):
            return TupleType(
                items=tuple(substitute_typevars(item, substitutions) for item in items),
            )

        case ColumnType(type=items_type):
            return ColumnType(
                type=substitute_typevars(items_type, substitutions),
            )

        case DataFrameType(columns=columns):
            return DataFrameType(
                columns=list(map(sub_column, columns)),
            )

        case FrameGroupBy(frame=frame):
            return FrameGroupBy(
                frame=cast(DataFrameType, substitute_typevars(frame, substitutions))
            )

        case UnknownType() | UnitType():
            return type

        case TopType() | GenericType():
            raise NotImplementedError(f"Unsupported type {type}")

        # Ensure exhaustiveness
        case _:
            assert_never(type)


def unfold_type(type: Type) -> Type:
    match type:
        case DerivedType(type=ref_type):
            return unfold_type(ref_type)
        case _:
            return type


def to_annotation(type: Type) -> str:
    def _args_annotation(func: Function) -> str:
        if len(func.kw_args) != 0:
            return "..."

        args: str = ", ".join(
            to_annotation(arg.type) for arg in func.pos_args + func.args
        )
        return f"[{args}]"

    match type:
        case TopType():
            return "Any"

        case BaseType(name=name):
            return name

        case DerivedType(name=name):
            return name

        case UnknownType():
            return "Any"

        case UnitType():
            return "None"

        case Function(returns=returns):
            params_annot: str = _args_annotation(type)
            return f"Callable[{params_annot}, {to_annotation(returns)}]"

        case OverloadedFunction():
            return "Callable"

        case ComplexType() | ExtensionType():
            raise NotImplementedError

        case TypeVar(name=name):
            return name

        case GenericType(name=name, params=params):
            return f"{name}[{', '.join(map(to_annotation, params))}]"

        case AppliedType(name=name, args=args):
            return f"{name}[{', '.join(map(to_annotation, args))}]"

        case ConstraintType():
            return str(type)

        case TupleType(items=items):
            return f"Tuple[{', '.join(map(to_annotation, items))}]"

        case ColumnType():
            return "pd.Series"

        case DataFrameType():
            return "pd.DataFrame"

        case FrameGroupBy():
            return "pd.api.typing.DataFrameGroupBy"

        case _:
            assert_never(type)


@dataclass(frozen=True, kw_only=True)
class Predicate:
    type: Type
    body: m.Expr
    alias: bool


Type = (
    TopType
    | BaseType
    | DerivedType
    | UnknownType
    | UnitType
    | Function
    | OverloadedFunction
    | ComplexType
    | ExtensionType
    | TypeVar
    | GenericType
    | AppliedType
    | ConstraintType
    | TupleType
    | ColumnType
    | DataFrameType
    | FrameGroupBy
)
