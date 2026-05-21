from __future__ import annotations

import io
from contextlib import contextmanager
from enum import Enum, auto
from typing import Generator, Generic, Optional, Protocol, TypeVar

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
    def _child_level(self, single: bool = False) -> Generator[None, None, None]:
        self._levels.append(_Level.LAST if single else _Level.ACTIVE)
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
            with self._child_level(single=True):
                child.accept(self)


class MidasAstPrinter(AstPrinter, m.Expr.Visitor[None], m.Stmt.Visitor[None]):
    #Statements

    def visit_simple_type_stmt(self, stmt: m.SimpleTypeStmt):
        self._write_line("SimpleTypeStmt")
        with self._child_level():
            self._write_line(f'name: "{stmt.name.lexeme}"')
            self._write_optional_child("template", stmt.template)
            self._write_line("base")
            with self._child_level(single=True):
                stmt.base.accept(self)
            self._write_optional_child("constraint", stmt.constraint, last=True)

    def visit_complex_type_stmt(self, stmt: m.ComplexTypeStmt):
        self._write_line("ComplexTypeStmt")
        with self._child_level():
            self._write_line(f'name: "{stmt.name.lexeme}"')
            self._write_optional_child("template", stmt.template)
            self._write_line("properties", last=True)
            with self._child_level():
                for i, prop in enumerate(stmt.properties):
                    self._idx = i
                    if i == len(stmt.properties) - 1:
                        self._mark_last()
                    prop.accept(self)

    def visit_property_stmt(self, stmt: m.PropertyStmt):
        self._write_line("PropertyStmt")
        with self._child_level():
            self._write_line(f'name: "{stmt.name.lexeme}"')
            self._write_line("type")
            with self._child_level(single=True):
                stmt.type.accept(self)
            self._write_optional_child("constraint", stmt.constraint, last=True)

    def visit_extend_stmt(self, stmt: m.ExtendStmt) -> None:
        self._write_line("ExtendStmt")
        with self._child_level():
            self._write_line("type")
            with self._child_level(single=True):
                stmt.type.accept(self)
            self._write_line("operations", last=True)
            with self._child_level():
                for i, op in enumerate(stmt.operations):
                    self._idx = i
                    if i == len(stmt.operations) - 1:
                        self._mark_last()
                    op.accept(self)

    def visit_op_stmt(self, stmt: m.OpStmt) -> None:
        self._write_line("OpStmt")
        with self._child_level():
            self._write_line(f'name: "{stmt.name.lexeme}"')

            self._write_line("operand")
            with self._child_level(single=True):
                stmt.operand.accept(self)

            self._write_line("result", last=True)
            with self._child_level(single=True):
                stmt.result.accept(self)

    def visit_predicate_stmt(self, stmt: m.PredicateStmt):
        self._write_line("PredicateStmt")
        with self._child_level():
            self._write_line(f'name: "{stmt.name.lexeme}"')
            self._write_line(f'subject: "{stmt.subject.lexeme}"')
            self._write_line("type")
            with self._child_level(single=True):
                stmt.type.accept(self)
            self._write_line("condition", last=True)
            with self._child_level(single=True):
                stmt.condition.accept(self)

    # Expressions

    def visit_simple_type_expr(self, expr: m.SimpleTypeExpr):
        self._write_line("SimpleTypeExpr")
        with self._child_level():
            self._write_line(f'name: "{expr.name.lexeme}"')
            self._write_line(f"optional: {expr.optional}", last=True)

    def visit_logical_expr(self, expr: m.LogicalExpr):
        self._write_line("LogicalExpr")
        with self._child_level():
            self._write_line("left")
            with self._child_level(single=True):
                expr.left.accept(self)

            self._write_line(f"operator: {expr.operator.lexeme}")

            self._write_line("right", last=True)
            with self._child_level(single=True):
                expr.right.accept(self)

    def visit_binary_expr(self, expr: m.BinaryExpr):
        self._write_line("BinaryExpr")
        with self._child_level():
            self._write_line("left")
            with self._child_level(single=True):
                expr.left.accept(self)

            self._write_line(f"operator: {expr.operator.lexeme}")

            self._write_line("right", last=True)
            with self._child_level(single=True):
                expr.right.accept(self)

    def visit_unary_expr(self, expr: m.UnaryExpr):
        self._write_line("UnaryExpr")
        with self._child_level():
            self._write_line(f"operator: {expr.operator.lexeme}")

            self._write_line("right", last=True)
            with self._child_level(single=True):
                expr.right.accept(self)

    def visit_get_expr(self, expr: m.GetExpr):
        self._write_line("GetExpr")
        with self._child_level():
            self._write_line("expr")
            with self._child_level(single=True):
                expr.expr.accept(self)
            self._write_line(f'name: "{expr.name.lexeme}"', last=True)

    def visit_variable_expr(self, expr: m.VariableExpr):
        self._write_line("VariableExpr")
        with self._child_level():
            self._write_line(f'name: "{expr.name.lexeme}"', last=True)

    def visit_grouping_expr(self, expr: m.GroupingExpr):
        self._write_line("GroupingExpr")
        with self._child_level():
            self._write_line("expr", last=True)
            with self._child_level(single=True):
                expr.expr.accept(self)

    def visit_literal_expr(self, expr: m.LiteralExpr) -> None:
        self._write_line("LiteralExpr")
        with self._child_level():
            self._write_line(f"value: {expr.value}", last=True)

    def visit_wildcard_expr(self, expr: m.WildcardExpr) -> None:
        self._write_line("WildcardExpr")

    def visit_template_expr(self, expr: m.TemplateExpr) -> None:
        self._write_line("TemplateExpr")
        with self._child_level(single=True):
            self._write_line("type")
            with self._child_level(single=True):
                expr.type.accept(self)

    def visit_type_expr(self, expr: m.TypeExpr):
        self._write_line("TypeExpr")
        with self._child_level():
            self._write_line(f'name: "{expr.name.lexeme}"')
            self._write_optional_child("template", expr.template)
            self._write_line(f"optional: {expr.optional}", last=True)


class MidasPrinter(m.Expr.Visitor[str], m.Stmt.Visitor[str]):
    def __init__(self, indent: int = 4):
        self.indent: int = indent
        self.level: int = 0

    def indented(self, text: str) -> str:
        return " " * (self.level * self.indent) + text

    def print(self, expr: m.Expr | m.Stmt):
        self.level = 0
        return expr.accept(self)

    def visit_type_stmt(self, stmt: m.TypeStmt):
        bases: list[str] = [b.accept(self) for b in stmt.bases]

        res: str = self.indented(f"type {stmt.name.lexeme}<{', '.join(bases)}>")
        if stmt.body is not None:
            res += " {\n"
            self.level += 1
            res += stmt.body.accept(self)
            self.level -= 1
            res += "\n" + self.indented("}")

        return res

    def visit_property_stmt(self, stmt: m.PropertyStmt):
        return f"{stmt.name.lexeme}: {stmt.type.accept(self)}"

    def visit_op_stmt(self, stmt: m.OpStmt):
        left: str = stmt.left.accept(self)
        op: str = stmt.op.lexeme
        right: str = stmt.right.accept(self)
        result: str = stmt.result.accept(self)
        return self.indented(f"op <{left}> {op} <{right}> = <{result}>")

    def visit_constraint_stmt(self, stmt: m.ConstraintStmt):
        name: str = stmt.name.lexeme
        constraint: str = stmt.constraint.accept(self)
        return self.indented(f"constraint {name} = {constraint}")

    def visit_type_expr(self, expr: m.TypeExpr):
        parts: list[str] = [expr.name.lexeme]
        for constraint in expr.constraints:
            parts.append("(" + constraint.accept(self) + ")")
        return " + ".join(parts)

    def visit_constraint_expr(self, expr: m.ConstraintExpr):
        parts: list[str] = [
            expr.left.accept(self),
            expr.op.lexeme,
            expr.right.accept(self),
        ]
        return " ".join(parts)

    def visit_type_body_expr(self, expr: m.TypeBodyExpr):
        properties: list[str] = [
            self.indented(prop.accept(self)) for prop in expr.properties
        ]
        return "\n".join(properties)

    def visit_wildcard_expr(self, expr: m.WildcardExpr):
        return "_"

    def visit_literal_expr(self, expr: m.LiteralExpr):
        return str(expr.value)
