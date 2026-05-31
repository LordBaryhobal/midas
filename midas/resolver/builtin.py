from __future__ import annotations

from typing import TYPE_CHECKING

from midas.checker.types import BaseType, Type

if TYPE_CHECKING:
    from midas.resolver.midas import MidasResolver


def basic_op(ctx: MidasResolver, type: Type, op: str):
    ctx.define_operation(
        left=type,
        operator=op,
        right=type,
        result=type,
    )


def define_builtins(ctx: MidasResolver):
    """Define builtin types and operations"""
    bool = ctx.define_type("bool", BaseType(name="bool"))
    int = ctx.define_type("int", BaseType(name="int"))
    float = ctx.define_type("float", BaseType(name="float"))
    str = ctx.define_type("str", BaseType(name="str"))

    basic_op(ctx, int, "__add__")
    basic_op(ctx, int, "__sub__")
    basic_op(ctx, int, "__mul__")
    basic_op(ctx, int, "__pow__")
    basic_op(ctx, int, "__mod__")
    basic_op(ctx, int, "__and__")
    basic_op(ctx, int, "__or__")
    basic_op(ctx, int, "__xor__")
    basic_op(ctx, float, "__add__")
    basic_op(ctx, float, "__sub__")
    basic_op(ctx, float, "__mul__")
    basic_op(ctx, float, "__truediv__")
    basic_op(ctx, str, "__add__")
