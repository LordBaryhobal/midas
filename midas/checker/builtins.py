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
    "object": {"float", "list", "dict", "str", "bytes", "tuple"},
    "float": {"int"},
}
"""
Hard-coded subtype relationships between builtin types

Circular dependencies and diamond inheritance MUST be avoided
"""


def define_builtins(reg: TypesRegistry):
    """Define builtin types and operations

    Args:
        reg (TypesRegistry): the types registry
    """
    any = reg.define_type("Any", TopType())
    unit = reg.define_type("None", UnitType())
    object = reg.define_type("object", BaseType(name="object"))
    bytes = reg.define_type("bytes", BaseType(name="bytes"))
    bool = reg.define_type("bool", BaseType(name="bool"))
    int = reg.define_type("int", BaseType(name="int"))
    float = reg.define_type("float", BaseType(name="float"))
    str = reg.define_type("str", BaseType(name="str"))
    slice = reg.define_type("slice", BaseType(name="slice"))

    tuple = reg.define_type("tuple", BaseType(name="tuple"))

    list = reg.define_type(
        "list",
        GenericType(
            name="list",
            params=[TypeVar(name="T", bound=None)],
            body=BaseType(name="list"),
        ),
    )
    dict = reg.define_type(
        "dict",
        GenericType(
            name="dict",
            params=[
                TypeVar(name="K", bound=None),
                TypeVar(name="V", bound=None),
            ],
            body=BaseType(name="dict"),
        ),
    )
