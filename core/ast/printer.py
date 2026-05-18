from __future__ import annotations

from contextlib import contextmanager
from enum import Enum, auto
import io
from typing import Generator, Generic, Optional, Protocol, TypeVar

import core.ast.annotations as a
import core.ast.midas as m


class _Level(Enum):
    EMPTY = auto()
    ACTIVE = auto()
    LAST = auto()


class Expr(Protocol):
    def accept(self, printer: AstPrinter) -> None: ...


T = TypeVar("T", bound=Expr)


class AstPrinter(Generic[T]):
    LAST_CHILD = "└── "
    CHILD = "├── "
    VERTICAL = "│   "
    EMPTY = "    "

    def __init__(self):
        self._levels: list[_Level] = []
        self._idx: Optional[int] = None
        self._buf: io.StringIO = io.StringIO()

    def print(self, expr: T):
        self._buf = io.StringIO()
        expr.accept(self)
        return self._buf.getvalue()

    @contextmanager
    def _child_level(self, last: bool = False) -> Generator[None, None, None]:
        self._levels.append(_Level.LAST if last else _Level.ACTIVE)
        try:
            yield
        finally:
            self._levels.pop()

    def _mark_last(self):
        if self._levels:
            self._levels[-1] = _Level.LAST

    def _write_line(self, text: str, *, last: bool = False):
        if last:
            self._mark_last()
        indent: str = self._build_indent()
        if self._idx is not None:
            text = f"[{self._idx}] {text}"
            self._idx = None
        self._buf.write(indent + text + "\n")

    def _build_indent(self) -> str:
        parts: list[str] = []
        for level in self._levels[:-1]:
            parts.append(self.EMPTY if level == _Level.EMPTY else self.VERTICAL)
        if self._levels:
            if self._levels[-1] == _Level.LAST:
                parts.append(self.LAST_CHILD)
                self._levels[-1] = _Level.EMPTY
            else:
                parts.append(self.CHILD)
        return "".join(parts)

    def _write_optional_child(
        self, label: str, child: Optional[T], *, last: bool = False
    ):
        if last:
            self._mark_last()
        if child is None:
            self._write_line(f"{label}: None")
        else:
            self._write_line(label)
            with self._child_level(last=True):
                child.accept(self)


class AnnotationAstPrinter(AstPrinter, a.Expr.Visitor[None], a.Stmt.Visitor[None]):
    def visit_annotation_stmt(self, stmt: a.AnnotationStmt) -> None:
        self._write_line("AnnotationStmt")
        with self._child_level():
            self._write_line(f'name: "{stmt.name.lexeme}"')
            self._write_optional_child("schema", stmt.schema, last=True)

    def visit_type_expr(self, expr: a.TypeExpr):
        self._write_line("TypeExpr")
        with self._child_level():
            self._write_line(f'name: "{expr.name.lexeme}"')
            self._write_line("constraints", last=True)
            with self._child_level():
                for i, constraint in enumerate(expr.constraints):
                    self._idx = i
                    if i == len(expr.constraints) - 1:
                        self._mark_last()
                    constraint.accept(self)
    
    def visit_constraint_expr(self, expr: a.ConstraintExpr) -> None:
        self._write_line("ConstraintExpr")
        with self._child_level():
            self._write_line("left")
            with self._child_level():
                self._mark_last()
                expr.left.accept(self)
            
            self._write_line(f"operator: {expr.op.lexeme}")
            
            self._write_line("right", last=True)
            with self._child_level():
                self._mark_last()
                expr.right.accept(self)

    def visit_schema_expr(self, expr: a.SchemaExpr):
        self._write_line("SchemaExpr")
        with self._child_level():
            for i, elmt in enumerate(expr.elements):
                self._idx = i
                if i == len(expr.elements) - 1:
                    self._mark_last()
                elmt.accept(self)

    def visit_schema_element_expr(self, expr: a.SchemaElementExpr):
        self._write_line("SchemaElementExpr")
        with self._child_level():
            name_text: str = "None" if expr.name is None else f'"{expr.name.lexeme}"'
            self._write_line(f"name: {name_text}")
            self._write_optional_child("type", expr.type, last=True)
    
    def visit_wildcard_expr(self, expr: a.WildcardExpr) -> None:
        self._write_line("WildcardExpr")
    
    def visit_literal_expr(self, expr: a.LiteralExpr) -> None:
        self._write_line("LiteralExpr")
        with self._child_level():
            self._write_line(f'value: {expr.value}', last=True)


class AnnotationPrinter(a.Expr.Visitor[str], a.Stmt.Visitor[str]):
    def print(self, expr: a.Expr | a.Stmt):
        return expr.accept(self)

    def visit_annotation_stmt(self, stmt: a.AnnotationStmt) -> str:
        schema: str = ""
        if stmt.schema is not None:
            schema = stmt.schema.accept(self)
        return f"{stmt.name.lexeme}{schema}"

    def visit_type_expr(self, expr: a.TypeExpr) -> str:
        parts: list[str] = [expr.name.lexeme]
        for constraint in expr.constraints:
            parts.append("(" + constraint.accept(self) + ")")
        return " + ".join(parts)
    
    def visit_constraint_expr(self, expr: a.ConstraintExpr) -> str:
        parts: list[str] = [
            expr.left.accept(self),
            expr.op.lexeme,
            expr.right.accept(self)
        ]
        return " ".join(parts)

    def visit_schema_expr(self, expr: a.SchemaExpr) -> str:
        res: str = expr.left.lexeme
        res += ", ".join(elmt.accept(self) for elmt in expr.elements)
        res += expr.right.lexeme
        return res

    def visit_schema_element_expr(self, expr: a.SchemaElementExpr) -> str:
        parts: list[str] = []
        if expr.name is not None:
            parts.append(expr.name.lexeme)

        if expr.type is None:
            parts.append("_")
        else:
            parts.append(expr.type.accept(self))
        return ": ".join(parts)

    def visit_wildcard_expr(self, expr: a.WildcardExpr) -> str:
        return "_"

    def visit_literal_expr(self, expr: a.LiteralExpr) -> str:
        return str(expr.value)


class MidasAstPrinter(AstPrinter, m.Expr.Visitor[None], m.Stmt.Visitor[None]):
    def visit_type_stmt(self, stmt: m.TypeStmt):
        self._write_line("TypeStmt")
        with self._child_level():
            self._write_line(f'name: "{stmt.name.lexeme}"')
            self._write_line("bases")
            with self._child_level():
                for i, base in enumerate(stmt.bases):
                    self._idx = i
                    if i == len(stmt.bases) - 1:
                        self._mark_last()
                    base.accept(self)
            self._write_optional_child("body", stmt.body, last=True)

    def visit_property_stmt(self, stmt: m.PropertyStmt):
        self._write_line("PropertyStmt")
        with self._child_level():
            self._write_line(f'name: "{stmt.name.lexeme}"')
            self._write_line("type", last=True)
            with self._child_level():
                self._mark_last()
                stmt.type.accept(self)

    def visit_op_stmt(self, stmt: m.OpStmt) -> None:
        self._write_line("OpStmt")
        with self._child_level():
            self._write_line("left")
            with self._child_level():
                self._mark_last()
                stmt.left.accept(self)

            self._write_line(f'op: "{stmt.op.lexeme}"')

            self._write_line("right")
            with self._child_level():
                self._mark_last()
                stmt.right.accept(self)

            self._write_line("result", last=True)
            with self._child_level():
                self._mark_last()
                stmt.result.accept(self)

    def visit_constraint_stmt(self, stmt: m.ConstraintStmt):
        self._write_line("ConstraintStmt")
        with self._child_level():
            self._write_line(f'name: "{stmt.name.lexeme}"')
            self._write_line("constraint", last=True)
            with self._child_level():
                self._mark_last()
                stmt.constraint.accept(self)

    def visit_type_expr(self, expr: m.TypeExpr):
        self._write_line("TypeExpr")
        with self._child_level():
            self._write_line(f'name: "{expr.name.lexeme}"')
            self._write_line("constraints", last=True)
            with self._child_level():
                for i, constraint in enumerate(expr.constraints):
                    self._idx = i
                    if i == len(expr.constraints) - 1:
                        self._mark_last()
                    constraint.accept(self)

    def visit_constraint_expr(self, expr: m.ConstraintExpr):
        self._write_line("ConstraintExpr")

    def visit_type_body_expr(self, expr: m.TypeBodyExpr):
        self._write_line("TypeBodyExpr")
        with self._child_level():
            self._write_line("properties", last=True)
            with self._child_level():
                for i, property in enumerate(expr.properties):
                    self._idx = i
                    if i == len(expr.properties) - 1:
                        self._mark_last()
                    property.accept(self)
