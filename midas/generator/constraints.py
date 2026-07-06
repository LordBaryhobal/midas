import ast
from typing import Optional

import midas.ast.midas as m
from midas.checker.registry import TypesRegistry
from midas.checker.types import (
    Function,
    ParamSpec,
    Predicate,
    Type,
    to_annotation,
)
from midas.lexer.token import TokenType

LOGICAL_OPERATORS: dict[TokenType, type[ast.boolop]] = {
    TokenType.AND: ast.And,
    # TokenType.OR: ast.Or,
}

BINARY_OPERATORS: dict[TokenType, type[ast.operator]] = {
    TokenType.PLUS: ast.Add,
    TokenType.MINUS: ast.Sub,
    TokenType.STAR: ast.Mult,
    TokenType.SLASH: ast.Div,
}

UNARY_OPERATORS: dict[TokenType, type[ast.unaryop]] = {
    TokenType.PLUS: ast.UAdd,
    TokenType.MINUS: ast.USub,
}

COMPARISON_OPERATORS: dict[TokenType, type[ast.cmpop]] = {
    TokenType.GREATER: ast.Gt,
    TokenType.GREATER_EQUAL: ast.GtE,
    TokenType.LESS: ast.Lt,
    TokenType.LESS_EQUAL: ast.LtE,
    TokenType.EQUAL_EQUAL: ast.Eq,
    TokenType.BANG_EQUAL: ast.NotEq,
}


class ConstraintGenerator(m.Expr.Visitor[ast.expr]):
    def __init__(self, types: TypesRegistry):
        self.types: TypesRegistry = types
        self._id: int = 0
        self._definitions: list[ast.stmt] = []
        self._aliases: dict[str, str] = {}

    def get_definitions(self) -> list[ast.stmt]:
        return self._definitions

    def generate(self, expr: m.Expr) -> ast.expr:
        match expr:
            case m.VariableExpr():
                return expr.accept(self)
            case _:
                func = Function(
                    params=ParamSpec(
                        mixed=[
                            Function.Parameter(
                                pos=0,
                                name="_",
                                type=self.types.get_type("Any"),
                                required=True,
                            )
                        ],
                    ),
                    returns=self.types.get_type("bool"),
                )
                alias: str = self.make_alias(None)
                definition: ast.stmt = self.make_definition(
                    alias, Predicate(type=func, body=expr, alias=False)
                )
                self._definitions.append(definition)
                return ast.Name(id=alias)

    def make_alias(self, name: Optional[str]) -> str:
        suffix: str
        if name is None:
            suffix = f"p{self._id}"
            self._id += 1
        else:
            suffix = name
        alias: str = f"__midas_{suffix}__"
        return alias

    def make_definition(self, name: str, predicate: Predicate) -> ast.stmt:
        body: ast.expr = predicate.body.accept(self)
        if predicate.alias:
            return ast.Assign(
                targets=[
                    ast.Name(id=name),
                ],
                value=body,
            )
        return self.make_func(name, [ast.Return(value=body)], predicate.type)

    def make_args(self, params: ParamSpec) -> ast.arguments:
        return ast.arguments(
            posonlyargs=[
                ast.arg(
                    arg=param.name,
                    annotation=ast.Constant(value=to_annotation(param.type)),
                )
                for param in params.pos
            ],
            args=[
                ast.arg(
                    arg=param.name,
                    annotation=ast.Constant(value=to_annotation(param.type)),
                )
                for param in params.mixed
            ],
            kwonlyargs=[
                ast.arg(
                    arg=param.name,
                    annotation=ast.Constant(value=to_annotation(param.type)),
                )
                for param in params.kw
            ],
            defaults=[],
            kw_defaults=[],
        )

    def make_func(
        self, name: str, inner_body: list[ast.stmt], type: Type, level: int = 0
    ) -> ast.stmt:
        match type:
            case Function(params=params, returns=Function()):
                inner_name: str = f"inner{level}"
                return ast.FunctionDef(
                    name=name,
                    args=self.make_args(params),
                    body=[
                        self.make_func(inner_name, inner_body, type.returns, level + 1),
                        ast.Return(value=ast.Name(id=inner_name)),
                    ],
                    returns=ast.Constant(value=to_annotation(type.returns)),
                    decorator_list=[],
                )

            case Function(params=params):
                return ast.FunctionDef(
                    name=name,
                    args=self.make_args(params),
                    body=inner_body,
                    returns=ast.Constant(value=to_annotation(type.returns)),
                    decorator_list=[],
                )

            case _:
                raise ValueError(f"Expected function, got {type!r}")

    def get_predicate(self, name: str) -> Optional[ast.expr]:
        if name not in self._aliases:
            predicate: Optional[Predicate] = self.types.lookup_predicate(name)
            if predicate is None:
                return None
            alias: str = self.make_alias(name)
            self._aliases[name] = alias
            self._definitions.append(self.make_definition(alias, predicate))

        return ast.Name(id=self._aliases[name])

    def visit_logical_expr(self, expr: m.LogicalExpr) -> ast.expr:
        return ast.BoolOp(
            op=LOGICAL_OPERATORS[expr.operator.type](),
            values=[
                expr.left.accept(self),
                expr.right.accept(self),
            ],
        )

    def visit_binary_expr(self, expr: m.BinaryExpr) -> ast.expr:
        op: TokenType = expr.operator.type
        if op in BINARY_OPERATORS:
            return ast.BinOp(
                left=expr.left.accept(self),
                op=BINARY_OPERATORS[op](),
                right=expr.right.accept(self),
            )
        if op in COMPARISON_OPERATORS:
            return ast.Compare(
                left=expr.left.accept(self),
                ops=[COMPARISON_OPERATORS[op]()],
                comparators=[expr.right.accept(self)],
            )
        raise ValueError(f"Unexpected binary operator {op}")

    def visit_unary_expr(self, expr: m.UnaryExpr) -> ast.expr:
        return ast.UnaryOp(
            op=UNARY_OPERATORS[expr.operator.type](),
            operand=expr.right.accept(self),
        )

    def visit_call_expr(self, expr: m.CallExpr) -> ast.expr:
        return ast.Call(
            func=expr.callee.accept(self),
            args=[arg.accept(self) for arg in expr.arguments],
            keywords=[
                ast.keyword(arg=name, value=arg.accept(self))
                for name, arg in expr.keywords.items()
            ],
        )

    def visit_get_expr(self, expr: m.GetExpr) -> ast.expr:
        return ast.Attribute(
            value=expr.expr.accept(self),
            attr=expr.name.lexeme,
        )

    def visit_variable_expr(self, expr: m.VariableExpr) -> ast.expr:
        name: str = expr.name.lexeme
        if (p := self.get_predicate(name)) is not None:
            return p
        return ast.Name(id=name)

    def visit_grouping_expr(self, expr: m.GroupingExpr) -> ast.expr:
        return expr.accept(self)

    def visit_literal_expr(self, expr: m.LiteralExpr) -> ast.expr:
        return ast.Constant(value=expr.value)

    def visit_wildcard_expr(self, expr: m.WildcardExpr) -> ast.expr:
        return ast.Name(id="_")
