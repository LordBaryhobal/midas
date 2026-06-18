import ast

import midas.ast.midas as m
from midas.lexer.token import TokenType

LOGICAL_OPERATORS: dict[TokenType, type[ast.boolop]] = {
    TokenType.AND: ast.And,
    # TokenType.OR: ast.Or,
}

BINARY_OPERATORS: dict[TokenType, type[ast.operator]] = {
    # TokenType.PLUS: ast.Add,
    TokenType.MINUS: ast.Sub,
    TokenType.STAR: ast.Mult,
    TokenType.SLASH: ast.Div,
}

UNARY_OPERATORS: dict[TokenType, type[ast.unaryop]] = {
    # TokenType.PLUS: ast.UAdd,
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
        # TODO: lookup predicate
        return ast.Name(id=expr.name.lexeme)

    def visit_grouping_expr(self, expr: m.GroupingExpr) -> ast.expr:
        return expr.accept(self)

    def visit_literal_expr(self, expr: m.LiteralExpr) -> ast.expr:
        return ast.Constant(value=expr.value)

    def visit_wildcard_expr(self, expr: m.WildcardExpr) -> ast.expr:
        return ast.Name(id="_")
