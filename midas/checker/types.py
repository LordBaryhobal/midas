from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Optional, assert_never, cast

import midas.ast.midas as m
from midas.ast.printer import MidasPrinter


@dataclass(frozen=True, kw_only=True)
class TopType:
    """The top type (`Any`)"""

    def __str__(self) -> str:
        return "Any"


@dataclass(frozen=True, kw_only=True)
class BaseType:
    """A base / builtin type"""

    name: str

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True, kw_only=True)
class DerivedType:
    """A derived type, i.e. a named subtype of another type"""

    name: str
    type: Type

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True, kw_only=True)
class UnknownType:
    """An unknown type"""

    def __str__(self) -> str:
        return "<Unknown>"


@dataclass(frozen=True, kw_only=True)
class UnitType:
    """The unit type (`None`)"""

    def __str__(self) -> str:
        return "None"


@dataclass(frozen=True, kw_only=True)
class Function:
    """A function type"""

    params: ParamSpec
    returns: Type

    def __str__(self) -> str:
        return f"{self.params} -> {self.returns}"

    @dataclass(frozen=True, kw_only=True)
    class Parameter:
        pos: int
        name: str
        type: Type
        required: bool
        unsupported: bool = False

        def __str__(self) -> str:
            opt: str = "" if self.required else "?"
            param: str = f"{self.name}: {self.type}{opt}"
            if self.unsupported:
                param = f"({param})"
            return param


@dataclass(frozen=True, kw_only=True)
class ParamSpec:
    """A function's parameter spec"""

    pos: list[Function.Parameter] = field(default_factory=list)
    mixed: list[Function.Parameter] = field(default_factory=list)
    kw: list[Function.Parameter] = field(default_factory=list)

    def __str__(self) -> str:
        params: list[str] = []
        if len(self.pos) != 0:
            params += list(map(str, self.pos))
            params.append("/")

        if len(self.mixed) != 0:
            params += list(map(str, self.mixed))

        if len(self.kw) != 0:
            params.append("*")
            params += list(map(str, self.kw))

        return f"({', '.join(params)})"


@dataclass(frozen=True, kw_only=True)
class OverloadedFunction:
    """A list of method overloads"""

    overloads: list[Type]

    def __str__(self) -> str:
        return "<overloaded function>"


class Variance(StrEnum):
    """The variance of a :class:`TypeVar`"""

    INVARIANT = "INVARIANT"
    COVARIANT = "COVARIANT"
    CONTRAVARIANT = "CONTRAVARIANT"


@dataclass(frozen=True, kw_only=True)
class TypeVar:
    """A type variable, often used as type parameters for a generic type"""

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
    """A generic type, with type parameters and a generic body type"""

    name: str
    params: list[TypeVar]
    body: Type

    def __str__(self) -> str:
        return f"{self.name}[{', '.join(map(str, self.params))}]"


@dataclass(frozen=True, kw_only=True)
class AppliedType:
    """An instance of a :class:`GenericType`, with concrete type arguments substituted in its body"""

    name: str
    args: list[Type]
    body: Type

    def __str__(self) -> str:
        return f"{self.name}[{', '.join(map(str, self.args))}]"


@dataclass(frozen=True, kw_only=True)
class ConstraintType:
    """A type with a constraint expression"""

    type: Type
    constraint: m.Expr

    def __str__(self) -> str:
        printer = MidasPrinter()
        return f"{self.type} where {printer.print(self.constraint)}"


@dataclass(frozen=True, kw_only=True)
class TupleType:
    """A tuple type, containing any number of ordered item types"""

    items: tuple[Type, ...]

    def __str__(self) -> str:
        return f"({', '.join(map(str, self.items))})"


@dataclass(frozen=True, kw_only=True)
class ColumnType:
    """A column type containing items of a given unique type"""

    type: Type

    def __str__(self) -> str:
        return f"Column[{self.type}]"


@dataclass(frozen=True, kw_only=True)
class DataFrameType:
    """A data-frame type, containing named columns of specific :class:`ColumnType`"""

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
    """A frame group-by object"""

    frame: DataFrameType

    def __str__(self) -> str:
        return f"FrameGroupBy[{self.frame}]"


@dataclass(frozen=True, kw_only=True)
class ColumnGroupBy:
    """A column group-by object"""

    column: ColumnType

    def __str__(self) -> str:
        return f"ColumnGroupBy[{self.column}]"


def substitute_typevars(type: Type, substitutions: dict[str, Type]) -> Type:
    """Substitute type variables in the given type

    This function is called recursively on inner type structures

    Args:
        type (Type): the type in which to substitute type variables
        substitutions (dict[str, Type]): a mapping of type variable names to
            concrete types

    Returns:
        Type: the resulting type with substitutions applied
    """

    def sub_parameter(param: Function.Parameter):
        return Function.Parameter(
            pos=param.pos,
            name=param.name,
            type=substitute_typevars(param.type, substitutions),
            required=param.required,
        )

    def sub_param_spec(spec: ParamSpec):
        return ParamSpec(
            pos=list(map(sub_parameter, spec.pos)),
            mixed=list(map(sub_parameter, spec.mixed)),
            kw=list(map(sub_parameter, spec.kw)),
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
            params=params,
            returns=returns,
        ):
            return Function(
                params=sub_param_spec(params),
                returns=substitute_typevars(returns, substitutions),
            )

        case OverloadedFunction(overloads=overloads):
            return OverloadedFunction(
                overloads=[
                    substitute_typevars(overload, substitutions)
                    for overload in overloads
                ]
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

        case ColumnGroupBy(column=column):
            return ColumnGroupBy(
                column=cast(ColumnType, substitute_typevars(column, substitutions))
            )

        case UnknownType() | UnitType():
            return type

        # Ensure exhaustiveness
        case _:
            assert_never(type)


def unfold_type(type: Type) -> Type:
    """Unfold a chain of :class:`DerivedType` to get the root supertype

    Args:
        type (Type): the type to unfold

    Returns:
        Type: the root supertype
    """
    match type:
        case DerivedType(type=ref_type):
            return unfold_type(ref_type)
        case _:
            return type


def to_annotation(type: Type) -> str:
    """Convert the given type to a Python annotation string

    Args:
        type (Type): the type to convert

    Returns:
        str: the annotation string
    """

    def _params_annotation(spec: ParamSpec) -> str:
        if len(spec.kw) != 0:
            return "..."

        params: str = ", ".join(
            to_annotation(param.type) for param in spec.pos + spec.mixed
        )
        return f"[{params}]"

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

        case Function(params=params, returns=returns):
            params_annot: str = _params_annotation(params)
            return f"Callable[{params_annot}, {to_annotation(returns)}]"

        case OverloadedFunction():
            return "Callable"

        case TypeVar(name=name):
            return name

        case GenericType(name=name, params=params):
            return f"{name}[{', '.join(map(to_annotation, params))}]"

        case AppliedType(name=name, args=args):
            return f"{name}[{', '.join(map(to_annotation, args))}]"

        case ConstraintType(type=base):
            return to_annotation(base)

        case TupleType(items=items):
            return f"Tuple[{', '.join(map(to_annotation, items))}]"

        case ColumnType():
            return "pd.Series"

        case DataFrameType():
            return "pd.DataFrame"

        case FrameGroupBy():
            return "pd.api.typing.DataFrameGroupBy"

        case ColumnGroupBy():
            return "pd.api.typing.SeriesGroupBy"

        case _:
            assert_never(type)


@dataclass(frozen=True, kw_only=True)
class Predicate:
    """A predicate"""

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
    | TypeVar
    | GenericType
    | AppliedType
    | ConstraintType
    | TupleType
    | ColumnType
    | DataFrameType
    | FrameGroupBy
    | ColumnGroupBy
)
