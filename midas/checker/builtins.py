from __future__ import annotations

from typing import TYPE_CHECKING

from midas.checker.types import (
    BaseType,
    GenericType,
    TopType,
    TypeVar,
    UnitType,
)

if TYPE_CHECKING:
    from midas.checker.registry import TypesRegistry


BUILTIN_SUBTYPES: dict[str, set[str]] = {
    "float": {"int"},
    "int": {"bool"},
}


def define_builtins(reg: TypesRegistry):
    """Define builtin types and operations"""
    any = reg.define_type("Any", TopType())
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
