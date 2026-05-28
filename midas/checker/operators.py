import ast
from typing import Type

OPERATOR_METHODS: dict[Type[ast.operator], str] = {
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

COMPARATOR_METHODS: dict[Type[ast.cmpop], str] = {
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
