import ast
from typing import Type

from midas.lexer.token import TokenType

PY_OPERATOR_METHODS: dict[Type[ast.operator], str] = {
    ast.Add: "__add__",
    ast.Sub: "__sub__",
    ast.Mult: "__mul__",
    ast.MatMult: "__matmul__",
    ast.Div: "__truediv__",
    ast.Mod: "__mod__",
    ast.Pow: "__pow__",
    ast.LShift: "__lshift__",
    ast.RShift: "__rshift__",
    ast.BitOr: "__or__",
    ast.BitXor: "__xor__",
    ast.BitAnd: "__and__",
    ast.FloorDiv: "__floordiv__",
}

PY_COMPARATOR_METHODS: dict[Type[ast.cmpop], str] = {
    ast.Eq: "__eq__",
    # ast.NotEq: "__noteq__",
    ast.Lt: "__lt__",
    ast.LtE: "__le__",
    ast.Gt: "__gt__",
    ast.GtE: "__ge__",
    # ast.Is: "__is__",
    # ast.IsNot: "__isnot__",
    # ast.In: "__in__",
    # ast.NotIn: "__notin__",
}

PY_UNARY_METHODS: dict[Type[ast.unaryop], str] = {
    ast.Invert: "__invert__",
    # ast.Not: "",
    ast.UAdd: "__pos__",
    ast.USub: "__neg__",
}


MIDAS_BINARY_METHODS: dict[TokenType, str] = {
    # TokenType.PLUS: "__add__",
    TokenType.MINUS: "__sub__",
    TokenType.STAR: "__mul__",
    TokenType.SLASH: "__truediv__",
    # TokenType.MODULO: "__mod__",
    # TokenType.POW: "__pow__",
    # ast.BitOr: "__or__",
    # ast.BitXor: "__xor__",
    # ast.BitAnd: "__and__",
    # ast.FloorDiv: "__floordiv__",
    TokenType.EQUAL_EQUAL: "__eq__",
    # ast.NotEq: "__noteq__",
    TokenType.LESS: "__lt__",
    TokenType.LESS_EQUAL: "__le__",
    TokenType.GREATER: "__gt__",
    TokenType.GREATER_EQUAL: "__ge__",
    # ast.Is: "__is__",
    # ast.IsNot: "__isnot__",
    # ast.In: "__in__",
    # ast.NotIn: "__notin__",
}

MIDAS_UNARY_METHODS: dict[TokenType, str] = {
    # ast.Invert: "__invert__",
    # ast.Not: "",
    # TokenType.PLUS: "__pos__",
    TokenType.MINUS: "__neg__",
}
