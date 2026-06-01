from __future__ import annotations

from typing import TYPE_CHECKING

from midas.checker.types import BaseType, Type, UnitType

if TYPE_CHECKING:
    from midas.resolver.midas import MidasResolver


def op(ctx: MidasResolver, t1: Type, operator: str, t2: Type, t3: Type):
    ctx.define_operation(
        left=t1,
        operator=operator,
        right=t2,
        result=t3,
    )

def basic_op(ctx: MidasResolver, type: Type, op: str):
    ctx.define_operation(
        left=type,
        operator=op,
        right=type,
        result=type,
    )


def define_builtins(ctx: MidasResolver):
    """Define builtin types and operations"""
    unit = ctx.define_type("None", UnitType())
    bool = ctx.define_type("bool", BaseType(name="bool"))
    int = ctx.define_type("int", BaseType(name="int"))
    float = ctx.define_type("float", BaseType(name="float"))
    str = ctx.define_type("str", BaseType(name="str"))

    basic_op(ctx, int, "__add__")  # int + int = int
    basic_op(ctx, int, "__sub__")  # int - int = int
    basic_op(ctx, int, "__mul__")  # int * int = int
    basic_op(ctx, int, "__pow__")  # int ** int = int
    basic_op(ctx, int, "__mod__")  # int % int = int
    basic_op(ctx, int, "__and__")  # int & int = int
    basic_op(ctx, int, "__or__")  # int | int = int
    basic_op(ctx, int, "__xor__")  # int ^ int = int
    op(ctx, int, "__lt__", int, bool)  # int < int = bool
    op(ctx, int, "__gt__", int, bool)  # int > int = bool
    op(ctx, int, "__le__", int, bool)  # int <= int = bool
    op(ctx, int, "__ge__", int, bool)  # int >= int = bool
    op(ctx, int, "__eq__", int, bool)  # int == int = bool
    basic_op(ctx, float, "__add__")  # float + float = float
    basic_op(ctx, float, "__sub__")  # float - float = float
    basic_op(ctx, float, "__mul__")  # float * float = float
    basic_op(ctx, float, "__truediv__")  # float / float = float
    op(ctx, float, "__lt__", float, bool)  # float < float = bool
    op(ctx, float, "__gt__", float, bool)  # float > float = bool
    op(ctx, float, "__le__", float, bool)  # float <= float = bool
    op(ctx, float, "__ge__", float, bool)  # float >= float = bool
    op(ctx, float, "__eq__", float, bool)  # float == float = bool
    basic_op(ctx, str, "__add__")  # str + str = str
    op(ctx, str, "__eq__", str, bool)  # str == str = bool

    op(ctx, int, "__lt__", float, bool)  # int < float = bool
    op(ctx, int, "__gt__", float, bool)  # int > float = bool
    op(ctx, int, "__le__", float, bool)  # int <= float = bool
    op(ctx, int, "__ge__", float, bool)  # int >= float = bool
    op(ctx, int, "__eq__", float, bool)  # int == float = bool

    op(ctx, float, "__lt__", int, bool)  # float < int = bool
    op(ctx, float, "__gt__", int, bool)  # float > int = bool
    op(ctx, float, "__le__", int, bool)  # float <= int = bool
    op(ctx, float, "__ge__", int, bool)  # float >= int = bool
    op(ctx, float, "__eq__", int, bool)  # float == int = bool