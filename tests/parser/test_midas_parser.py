import textwrap

import pytest

from core.ast.midas import (
    ConstraintExpr,
    ConstraintStmt,
    Expr,
    LiteralExpr,
    OpStmt,
    PropertyStmt,
    Stmt,
    TypeBodyExpr,
    TypeExpr,
    TypeStmt,
    WildcardExpr,
)
from lexer.midas import MidasLexer
from lexer.position import Position
from lexer.token import Token
from parser.midas import MidasParser


class AstSerializer(Stmt.Visitor[str], Expr.Visitor[str]):
    def serialize(self, stmt: Stmt):
        return stmt.accept(self)

    def visit_type_stmt(self, stmt: TypeStmt) -> str:
        res: str = f"(type_def {stmt.name.lexeme}"
        for base in stmt.bases:
            res += " " + base.accept(self)
        if stmt.body is not None:
            res += " " + stmt.body.accept(self)
        res += ")"
        return res

    def visit_type_expr(self, expr: TypeExpr) -> str:
        res: str = f"({expr.name.lexeme}"
        for constraint in expr.constraints:
            res += " " + constraint.accept(self)
        res += ")"
        return res

    def visit_constraint_expr(self, expr: ConstraintExpr) -> str:
        return f"(constraint {expr.left.accept(self)} {expr.op.lexeme} {expr.right.accept(self)})"

    def visit_wildcard_expr(self, expr: WildcardExpr) -> str:
        return "(_)"

    def visit_literal_expr(self, expr: LiteralExpr) -> str:
        return f"({expr.value})"

    def visit_type_body_expr(self, expr: TypeBodyExpr) -> str:
        res: str = "(body"
        for prop in expr.properties:
            res += " " + prop.accept(self)
        res += ")"
        return res

    def visit_property_stmt(self, stmt: PropertyStmt) -> str:
        return f"(property {stmt.name.lexeme} {stmt.type.accept(self)})"

    def visit_op_stmt(self, stmt: OpStmt) -> str:
        left: str = stmt.left.accept(self)
        right: str = stmt.right.accept(self)
        result: str = stmt.result.accept(self)
        return f"(op_def {left} {stmt.op.lexeme} {right} {result})"

    def visit_constraint_stmt(self, stmt: ConstraintStmt) -> str:
        return f"(constraint_def {stmt.name.lexeme} {stmt.constraint.accept(self)})"


def parse(source: str) -> list[Stmt]:
    tokens: list[Token] = MidasLexer(source).process()
    return MidasParser(tokens).parse()


def ast_str(source: str) -> list[str]:
    stmts: list[Stmt] = parse(source)
    return [AstSerializer().serialize(stmt) for stmt in stmts]


@pytest.mark.parametrize(
    "src,expected",
    [
        ("type Foo<>", "(type_def Foo)"),
        ("type Foo<Bar>", "(type_def Foo (Bar))"),
        ("type Foo<Bar, Baz>", "(type_def Foo (Bar) (Baz))"),
        (
            "type Foo<Bar + (_ < 2), Baz>",
            "(type_def Foo (Bar (constraint (_) < (2.0))) (Baz))",
        ),
        (
            """
            type Foo<> {
                foo: Bar
            }
            """,
            "(type_def Foo (body (property foo (Bar))))",
        ),
        (
            """
            type Foo<> {
                foo: Bar + (_ != none)
                foo2: Bar2 + (0 <= _) + (_ <= 100)
            }
            """,
            "(type_def Foo (body (property foo (Bar (constraint (_) != (None)))) (property foo2 (Bar2 (constraint (0.0) <= (_)) (constraint (_) <= (100.0))))))",
        ),
        ("op <A> + <B> = <C>", "(op_def (A) + (B) (C))"),
        (
            "op <A + (_ < 100)> + <B + (_ < 100)> = <C + (_ < 200)>",
            "(op_def (A (constraint (_) < (100.0))) + (B (constraint (_) < (100.0))) (C (constraint (_) < (200.0))))",
        ),
        (
            "constraint Positive = _ >= 0",
            "(constraint_def Positive (constraint (_) >= (0.0)))",
        ),
    ],
)
def test_expressions(src: str, expected: str | list[str]):
    if isinstance(expected, str):
        expected = [expected]
    assert ast_str(src) == expected


@pytest.mark.parametrize(
    "src,pos",
    [
        ###
        # Misc
        ###
        ("42", (1, 1)),
        ("true", (1, 1)),
        ("foo", (1, 1)),
        ###
        # Type statements
        ###
        ("type", (1, 5)),
        ("type true", (1, 6)),
        ("type Foo", (1, 9)),
        ("type Foo<1>", (1, 10)),
        # ("type Foo<float,>", (1, 16)),  # trailing comma is accepted, TODO: update parser or EBNF
        ("type Foo<float, 1>", (1, 17)),
        ("type Foo<float", (1, 15)),
        ("type Foo<float> { 3 }", (1, 19)),
        (
            """
            type Foo<float> {
                foo
            }
            """,
            (4, 1),
        ),
        (
            """
            type Foo<float> {
                foo: 3
            }
            """,
            (3, 10),
        ),
        ###
        # Operation statements
        ###
        ("op", (1, 3)),
        ("op float", (1, 4)),
        ("op <", (1, 5)),
        ("op <float", (1, 10)),
        ("op <float>", (1, 11)),
        ("op <float> +", (1, 13)),
        ("op <float> + float", (1, 14)),
        ("op <float> + <", (1, 15)),
        ("op <float> + <float", (1, 20)),
        ("op <float> + <float>", (1, 21)),
        ("op <float> + <float> =", (1, 23)),
        ("op <float> + <float> = float", (1, 24)),
        ("op <float> + <float> = <", (1, 25)),
        ("op <float> + <float> = <float", (1, 30)),
        ("op <float + 3> + <float> = <float>", (1, 13)),
        ("op <float> + <float + 3> = <float>", (1, 23)),
        ("op <float> + <float> = <float + 3>", (1, 33)),
        ###
        # Constraint statements
        ###
        ("constraint", (1, 11)),
        ("constraint 3", (1, 12)),
        ("constraint Foo", (1, 15)),
        ("constraint Foo =", (1, 17)),
        ("constraint Foo = 3", (1, 19)),
        ("constraint Foo = 3 <", (1, 21)),
    ],
)
def test_parsing_error(src: str, pos: tuple[int, int]):
    src = textwrap.dedent(src)
    tokens: list[Token] = MidasLexer(src).process()
    parser: MidasParser = MidasParser(tokens)
    stmt: list[Stmt] = parser.parse()
    assert len(stmt) == 0
    assert len(parser.errors) != 0
    error_pos: Position = parser.errors[0].token.position
    assert (error_pos.line, error_pos.column) == pos
