from typing import Optional

import pytest

from core.ast.annotations import (
    AnnotationStmt,
    ConstraintExpr,
    Expr,
    LiteralExpr,
    SchemaElementExpr,
    SchemaExpr,
    Stmt,
    TypeExpr,
    WildcardExpr,
)
from lexer.annotations import AnnotationLexer
from lexer.position import Position
from lexer.token import Token
from parser.annotations import AnnotationParser


class AstSerializer(Stmt.Visitor[str], Expr.Visitor[str]):
    def serialize(self, stmt: Stmt):
        return stmt.accept(self)

    def visit_annotation_stmt(self, stmt: AnnotationStmt) -> str:
        schema: str = ""
        if stmt.schema is not None:
            schema = " " + stmt.schema.accept(self)
        return f"(annotation {stmt.name.lexeme}{schema})"

    def visit_schema_expr(self, expr: SchemaExpr) -> str:
        elements: list[str] = [elmt.accept(self) for elmt in expr.elements]
        return f"(schema {' '.join(elements)})"

    def visit_schema_element_expr(self, expr: SchemaElementExpr) -> str:
        name: str = expr.name.lexeme if expr.name is not None else "_"
        type: str = expr.type.accept(self) if expr.type is not None else "_"
        return f"({name} {type})"

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


def parse(source: str) -> Optional[Stmt]:
    tokens: list[Token] = AnnotationLexer(source).process()
    return AnnotationParser(tokens).parse()


def must_parse(source: str) -> Stmt:
    stmt: Optional[Stmt] = parse(source)
    assert stmt is not None
    return stmt


def ast_str(source: str) -> str:
    stmt: Stmt = must_parse(source)
    return AstSerializer().serialize(stmt)


@pytest.mark.parametrize(
    "src,expected",
    [
        ("Type", "(annotation Type)"),
        ("Type[]", "(annotation Type (schema ))"),
        (
            """
            Frame[
                verified: bool,
                birth_year: int,
                height: float + ( _ > 0 ) + ( _ < 250 ),
                name: str,
                date: datetime,
                float,  # unnamed
                unknown: _,  # untyped
                _  # unnamed and untyped
            ]
            """,
            "(annotation Frame (schema (verified (bool)) (birth_year (int)) (height (float (constraint (_) > (0.0)) (constraint (_) < (250.0)))) (name (str)) (date (datetime)) (_ (float)) (unknown _) (_ _)))",
        ),
    ],
)
def test_expressions(src: str, expected: str):
    assert ast_str(src) == expected


@pytest.mark.parametrize(
    "src,pos,should_fail",
    [
        ("", (1, 1), True),
        ("42", (1, 1), True),
        ("True", (1, 1), True),
        ("Type[", (1, 6), True),
        ("Type[] Type2", (1, 8), False),
        ("Type[bool:]", (1, 11), True),
        ("Type[3]", (1, 6), True),
        ("Type[bool float]", (1, 11), True),
        ("Type[bool (_ < 2)]", (1, 11), True),
        ("Type[bool + _ < 2)]", (1, 13), True),
        ("Type[bool + (_ < 2]", (1, 19), True),
        ("Type[bool + (< 2)]", (1, 14), True),
        ("Type[bool + (_ + 2)]", (1, 16), True),
        ("Type[bool + (Foo + Bar)]", (1, 14), True),
        # ("Type[bool,]", (1, 11), True),  # trailing comma is accepted, TODO: update parser or EBNF
        ("Type[bool, Type[]]", (1, 16), True),
        ("Type[foo: 3]", (1, 11), True),
    ],
)
def test_parsing_error(src: str, pos: tuple[int, int], should_fail: bool):
    tokens: list[Token] = AnnotationLexer(src).process()
    parser: AnnotationParser = AnnotationParser(tokens)
    stmt: Optional[Stmt] = parser.parse()
    if should_fail:
        assert stmt is None
    assert len(parser.errors) != 0
    error_pos: Position = parser.errors[0].token.position
    assert (error_pos.line, error_pos.column) == pos
