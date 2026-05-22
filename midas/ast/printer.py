from __future__ import annotations

import ast
import io
from contextlib import contextmanager
from enum import Enum, auto
from typing import Generator, Generic, Optional, Protocol, TypeVar

import midas.ast.midas as m
import midas.ast.python as p


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
    # Statements

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

    def visit_simple_type_stmt(self, stmt: m.SimpleTypeStmt):
        template: str = stmt.template.accept(self) if stmt.template is not None else ""
        res: str = f"type {stmt.name.lexeme}{template}({stmt.base.accept(self)})"
        if stmt.constraint is not None:
            res += " where " + stmt.constraint.accept(self)
        return self.indented(res)

    def visit_complex_type_stmt(self, stmt: m.ComplexTypeStmt):
        template: str = stmt.template.accept(self) if stmt.template is not None else ""
        res: str = self.indented(f"type {stmt.name.lexeme}{template}")
        res += " {\n"
        self.level += 1
        for prop in stmt.properties:
            res += prop.accept(self)
            res += "\n"
        self.level -= 1
        res += self.indented("}")
        return res

    def visit_property_stmt(self, stmt: m.PropertyStmt):
        res: str = f"{stmt.name.lexeme}: {stmt.type.accept(self)}"
        if stmt.constraint is not None:
            res += " where " + stmt.constraint.accept(self)
        return self.indented(res)

    def visit_extend_stmt(self, stmt: m.ExtendStmt):
        res: str = self.indented(f"extend {stmt.type.accept(self)}")
        res += " {\n"
        self.level += 1
        for op in stmt.operations:
            res += op.accept(self)
        self.level -= 1
        res += "\n" + self.indented("}")
        return res

    def visit_op_stmt(self, stmt: m.OpStmt):
        operand: str = stmt.operand.accept(self)
        result: str = stmt.result.accept(self)
        return self.indented(f"op {stmt.name.lexeme}({operand}) -> {result}")

    def visit_predicate_stmt(self, stmt: m.PredicateStmt):
        name: str = stmt.name.lexeme
        subject: str = stmt.subject.lexeme
        type: str = stmt.type.accept(self)
        condition: str = stmt.condition.accept(self)
        return self.indented(f"predicate {name}({subject}: {type}) = {condition}")

    def visit_simple_type_expr(self, expr: m.SimpleTypeExpr):
        return f"{expr.name.lexeme}{'?' if expr.optional else ''}"

    def visit_logical_expr(self, expr: m.LogicalExpr):
        left: str = expr.left.accept(self)
        operator: str = expr.operator.lexeme
        right: str = expr.right.accept(self)
        return f"{left} {operator} {right}"

    def visit_binary_expr(self, expr: m.BinaryExpr):
        left: str = expr.left.accept(self)
        operator: str = expr.operator.lexeme
        right: str = expr.right.accept(self)
        return f"{left} {operator} {right}"

    def visit_unary_expr(self, expr: m.UnaryExpr):
        operator: str = expr.operator.lexeme
        right: str = expr.right.accept(self)
        return f"{operator}{right}"

    def visit_get_expr(self, expr: m.GetExpr):
        expr_: str = expr.expr.accept(self)
        name: str = expr.name.lexeme
        return f"{expr_}.{name}"

    def visit_variable_expr(self, expr: m.VariableExpr):
        return expr.name.lexeme

    def visit_grouping_expr(self, expr: m.GroupingExpr):
        expr_: str = expr.expr.accept(self)
        return f"({expr_})"

    def visit_literal_expr(self, expr: m.LiteralExpr):
        return str(expr.value)

    def visit_wildcard_expr(self, expr: m.WildcardExpr):
        return "_"

    def visit_template_expr(self, expr: m.TemplateExpr):
        return f"[{expr.type.accept(self)}]"

    def visit_type_expr(self, expr: m.TypeExpr):
        template: str = expr.template.accept(self) if expr.template is not None else ""
        return f"{expr.name.lexeme}{template}{'?' if expr.optional else ''}"


class PythonAstPrinter(AstPrinter, p.MidasType.Visitor[None]):
    def visit_base_type(self, node: p.BaseType) -> None:
        self._write_line("BaseType")
        with self._child_level():
            self._write_line(f"base: {node.base}")
            self._write_optional_child("param", node.param, last=True)

    def visit_constraint_type(self, node: p.ConstraintType) -> None:
        self._write_line("ConstraintType")
        with self._child_level():
            self._write_line("type")
            with self._child_level(single=True):
                node.type.accept(self)
            self._write_line(f"constraint: {ast.unparse(node.constraint)}", last=True)

    def visit_frame_column(self, node: p.FrameColumn) -> None:
        self._write_line("FrameColumn")
        with self._child_level():
            self._write_line(f"name: {node.name}")
            self._write_optional_child("type", node.type, last=True)

    def visit_frame_type(self, node: p.FrameType) -> None:
        self._write_line("FrameType")
        with self._child_level():
            self._write_line("columns", last=True)
            with self._child_level():
                for i, col in enumerate(node.columns):
                    self._idx = i
                    if i == len(node.columns) - 1:
                        self._mark_last()
                    col.accept(self)
