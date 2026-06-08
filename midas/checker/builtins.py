from midas.checker.registry import TypesRegistry
from midas.checker.types import BaseType, Type, UnitType

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
    bool = reg.define_type("bool", BaseType(name="bool"))
    int = reg.define_type("int", BaseType(name="int"))
    float = reg.define_type("float", BaseType(name="float"))
    str = reg.define_type("str", BaseType(name="str"))

    basic_op(reg, int, "__add__")  # int + int = int
    basic_op(reg, int, "__sub__")  # int - int = int
    basic_op(reg, int, "__mul__")  # int * int = int
    basic_op(reg, int, "__pow__")  # int ** int = int
    basic_op(reg, int, "__mod__")  # int % int = int
    basic_op(reg, int, "__and__")  # int & int = int
    basic_op(reg, int, "__or__")  # int | int = int
    basic_op(reg, int, "__xor__")  # int ^ int = int
    op(reg, int, "__lt__", int, bool)  # int < int = bool
    op(reg, int, "__gt__", int, bool)  # int > int = bool
    op(reg, int, "__le__", int, bool)  # int <= int = bool
    op(reg, int, "__ge__", int, bool)  # int >= int = bool
    op(reg, int, "__eq__", int, bool)  # int == int = bool
    basic_op(reg, float, "__add__")  # float + float = float
    basic_op(reg, float, "__sub__")  # float - float = float
    basic_op(reg, float, "__mul__")  # float * float = float
    basic_op(reg, float, "__truediv__")  # float / float = float
    op(reg, float, "__lt__", float, bool)  # float < float = bool
    op(reg, float, "__gt__", float, bool)  # float > float = bool
    op(reg, float, "__le__", float, bool)  # float <= float = bool
    op(reg, float, "__ge__", float, bool)  # float >= float = bool
    op(reg, float, "__eq__", float, bool)  # float == float = bool
    basic_op(reg, str, "__add__")  # str + str = str
    op(reg, str, "__eq__", str, bool)  # str == str = bool

    op(reg, int, "__lt__", float, bool)  # int < float = bool
    op(reg, int, "__gt__", float, bool)  # int > float = bool
    op(reg, int, "__le__", float, bool)  # int <= float = bool
    op(reg, int, "__ge__", float, bool)  # int >= float = bool
    op(reg, int, "__eq__", float, bool)  # int == float = bool

    op(reg, float, "__lt__", int, bool)  # float < int = bool
    op(reg, float, "__gt__", int, bool)  # float > int = bool
    op(reg, float, "__le__", int, bool)  # float <= int = bool
    op(reg, float, "__ge__", int, bool)  # float >= int = bool
    op(reg, float, "__eq__", int, bool)  # float == int = bool
