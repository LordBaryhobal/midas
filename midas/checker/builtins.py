from __future__ import annotations

from typing import TYPE_CHECKING

from midas.checker.types import (
    BaseType,
    GenericType,
    Type,
    TypeVar,
    UnitType,
)

if TYPE_CHECKING:
    from midas.checker.registry import TypesRegistry


BUILTIN_SUBTYPES: dict[str, set[str]] = {
    "float": {"int"},
    "int": {"bool"},
}


def op(reg: TypesRegistry, t1: Type, operator: str, t2: Type, t3: Type):
    reg.define_operation(
        left=t1,
        operator=operator,
        right=t2,
        result=t3,
    )


def basic_op(reg: TypesRegistry, type: Type, op: str):
    reg.define_operation(
        left=type,
        operator=op,
        right=type,
        result=type,
    )


def define_builtins(reg: TypesRegistry):
    """Define builtin types and operations"""
    unit = reg.define_type("None", UnitType())
    object = reg.define_type("object", BaseType(name="object"))
    bool = reg.define_type("bool", BaseType(name="bool"))
    int = reg.define_type("int", BaseType(name="int"))
    float = reg.define_type("float", BaseType(name="float"))
    str = reg.define_type("str", BaseType(name="str"))

    list = reg.define_type(
        "list",
        GenericType(
            name="list",
            params=[TypeVar(name="T", bound=None)],
            body=BaseType(name="list"),
        ),
    )
