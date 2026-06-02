from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Generic, Optional, Protocol, TextIO, TypeVar

import midas.ast.midas as m
import midas.ast.python as p
from midas.ast.location import Location
from midas.checker.diagnostic import Diagnostic
from midas.lexer.token import Token

H = TypeVar("H", bound="Highlighter", contravariant=True)


class Highlightable(Protocol, Generic[H]):
    def accept(self, visitor: H): ...


class Locatable(Protocol):
    @property
    @abstractmethod
    def location(self) -> Optional[Location]: ...


@dataclass(frozen=True)
class LocatableToken:
    token: Token

    @property
    def location(self) -> Location:
        return self.token.get_location()


class Highlighter(ABC):
    BASE_CSS_PATH: Path = Path(__file__).parent / "highlight.css"
    EXTRA_CSS_PATH: Optional[Path] = None

    def __init__(self, source: str) -> None:
        self.source: str = source
        self.lines: list[str] = self.source.splitlines()
        self.openings: dict[tuple[int, int], list[str]] = {}
        self.closings: dict[tuple[int, int], list[str]] = {}

    def format_css(self, path: Path) -> list[str]:
        css: str = path.read_text()
        css = "\n".join(("        " + line).rstrip() for line in css.splitlines())
        return [
            "    <style>",
            css,
            "    </style>",
        ]

    def dump(self, buf: TextIO):
        base_css: list[str] = self.format_css(self.BASE_CSS_PATH)
        extra_css: list[str] = (
            self.format_css(self.EXTRA_CSS_PATH)
            if self.EXTRA_CSS_PATH is not None
            else []
        )
        lines: list[str] = [
            "<!DOCTYPE html>",
            '<html lang="en">',
            "<head>",
            '    <meta charset="UTF-8">',
            '    <meta name="viewport" content="width=device-width, initial-scale=1.0">',
            "    <title>Highlighted file</title>",
            *base_css,
            *extra_css,
            "</head>",
            "<body>",
            '    <div id="code">',
        ]
        for l, line in enumerate(self.lines):
            lineno: int = l + 1
            line_buf: str = (
                f'<div class="line" id="l{lineno}"><div class="no">{lineno}</div><div class="txt">'
            )
            for c, char in enumerate(line):
                pos: tuple[int, int] = (lineno, c)
                closings: list[str] = self.closings.get(pos, [])
                openings: list[str] = self.openings.get(pos, [])
                line_buf += "".join(closings + openings)
                line_buf += char
            line_buf += "".join(self.closings.get((lineno, len(line)), []))
            line_buf += "</div></div>"
            lines.append("        " + line_buf)
        lines.extend(
            [
                "    </div>",
                "</body>",
                "</html>",
            ]
        )

        buf.write("\n".join(lines))

    def wrap(self, node: Locatable, cls: str, message: Optional[str] = None):
        if node.location is None:
            return
        if node.location.end_lineno is None or node.location.end_col_offset is None:
            return
        start_pos: tuple[int, int] = (node.location.lineno, node.location.col_offset)
        end_pos: tuple[int, int] = (
            node.location.end_lineno,
            node.location.end_col_offset,
        )
        opening: str = f'<span class="{cls}" title="{cls}">'
        closing: str = "</span>"
        if message is not None:
            opening = f'<span class="with-msg">{opening}'
            closing = f'{closing}<span class="message">{message}</span></span>'

        self.openings.setdefault(start_pos, []).append(opening)
        self.closings.setdefault(end_pos, []).insert(0, closing)
        if start_pos[0] != end_pos[0]:
            for l in range(start_pos[0], end_pos[0]):
                c: int = len(self.lines[l - 1])
                self.closings.setdefault((l, c), []).insert(0, closing)
                self.openings.setdefault((l + 1, 0), []).append(opening)


class PythonHighlighter(
    Highlighter,
    p.MidasType.Visitor[None],
    p.Stmt.Visitor[None],
    p.Expr.Visitor[None],
):
    EXTRA_CSS_PATH: Optional[Path] = Path(__file__).parent / "hl_python.css"

    def highlight(self, node: Highlightable[PythonHighlighter]):
        node.accept(self)

    def visit_base_type(self, node: p.BaseType) -> None:
        self.wrap(node, "base-type")
        if node.param is not None:
            self.wrap(node.param, "param")
            node.param.accept(self)

    def visit_constraint_type(self, node: p.ConstraintType) -> None:
        self.wrap(node, "constraint-type")
        node.type.accept(self)

    def visit_frame_column(self, node: p.FrameColumn) -> None:
        self.wrap(node, "frame-column")
        if node.type is not None:
            node.type.accept(self)

    def visit_frame_type(self, node: p.FrameType) -> None:
        self.wrap(node, "frame-type")
        for column in node.columns:
            column.accept(self)

    def visit_expression_stmt(self, stmt: p.ExpressionStmt) -> None:
        stmt.expr.accept(self)

    def visit_function(self, stmt: p.Function) -> None:
        self.wrap(stmt, "function")
        for arg in stmt.posonlyargs + stmt.args + stmt.kwonlyargs:
            self._highlight_function_argument(arg)
        for body_stmt in stmt.body:
            body_stmt.accept(self)

    def _highlight_function_argument(self, arg: p.Function.Argument) -> None:
        self.wrap(arg, "argument")
        if arg.type is not None:
            arg.type.accept(self)

    def visit_type_assign(self, stmt: p.TypeAssign) -> None:
        stmt.type.accept(self)

    def visit_assign_stmt(self, stmt: p.AssignStmt) -> None:
        for target in stmt.targets:
            target.accept(self)
        stmt.value.accept(self)

    def visit_return_stmt(self, stmt: p.ReturnStmt) -> None:
        self.wrap(stmt, "return")
        if stmt.value is not None:
            stmt.value.accept(self)

    def visit_if_stmt(self, stmt: p.IfStmt) -> None:
        self.wrap(stmt, "if")
        stmt.test.accept(self)
        for body_stmt in stmt.body:
            body_stmt.accept(self)
        for else_stmt in stmt.orelse:
            else_stmt.accept(self)

    def visit_binary_expr(self, expr: p.BinaryExpr) -> None: ...

    def visit_compare_expr(self, expr: p.CompareExpr) -> None: ...

    def visit_unary_expr(self, expr: p.UnaryExpr) -> None: ...

    def visit_call_expr(self, expr: p.CallExpr) -> None:
        self.wrap(expr, "call")
        expr.callee.accept(self)
        for arg in expr.arguments:
            arg.accept(self)
        for arg in expr.keywords.values():
            arg.accept(self)

    def visit_get_expr(self, expr: p.GetExpr) -> None: ...

    def visit_literal_expr(self, expr: p.LiteralExpr) -> None: ...

    def visit_variable_expr(self, expr: p.VariableExpr) -> None: ...

    def visit_logical_expr(self, expr: p.LogicalExpr) -> None: ...

    def visit_set_expr(self, expr: p.SetExpr) -> None: ...

    def visit_cast_expr(self, expr: p.CastExpr) -> None: ...

    def visit_ternary_expr(self, expr: p.TernaryExpr) -> None: ...


class MidasHighlighter(
    Highlighter, m.Stmt.Visitor[None], m.Expr.Visitor[None], m.Type.Visitor[None]
):
    EXTRA_CSS_PATH: Optional[Path] = Path(__file__).parent / "hl_midas.css"

    def highlight(self, node: Highlightable[MidasHighlighter]):
        node.accept(self)

    def visit_type_stmt(self, stmt: m.TypeStmt) -> None:
        self.wrap(stmt, "type-stmt")
        self.wrap(LocatableToken(stmt.name), "type-name")
        stmt.type.accept(self)

    def visit_property_stmt(self, stmt: m.PropertyStmt) -> None:
        self.wrap(stmt, "property")
        stmt.type.accept(self)

    def visit_extend_stmt(self, stmt: m.ExtendStmt) -> None:
        self.wrap(stmt, "extend")
        stmt.type.accept(self)
        for op in stmt.operations:
            op.accept(self)

    def visit_op_stmt(self, stmt: m.OpStmt) -> None:
        self.wrap(stmt, "op")
        self.wrap(LocatableToken(stmt.name), "op-name")
        stmt.operand.accept(self)
        stmt.result.accept(self)

    def visit_predicate_stmt(self, stmt: m.PredicateStmt) -> None:
        self.wrap(stmt, "predicate")
        self.wrap(LocatableToken(stmt.name), "predicate-name")
        stmt.type.accept(self)
        stmt.condition.accept(self)

    def visit_logical_expr(self, expr: m.LogicalExpr) -> None:
        self.wrap(expr, "logical-expr")
        expr.left.accept(self)
        expr.right.accept(self)

    def visit_binary_expr(self, expr: m.BinaryExpr) -> None:
        self.wrap(expr, "binary-expr")
        expr.left.accept(self)
        expr.right.accept(self)

    def visit_unary_expr(self, expr: m.UnaryExpr) -> None:
        self.wrap(expr, "unary-expr")
        expr.right.accept(self)

    def visit_get_expr(self, expr: m.GetExpr) -> None:
        self.wrap(expr, "get-expr")
        expr.expr.accept(self)

    def visit_variable_expr(self, expr: m.VariableExpr) -> None:
        self.wrap(expr, "variable")

    def visit_grouping_expr(self, expr: m.GroupingExpr) -> None:
        expr.expr.accept(self)

    def visit_literal_expr(self, expr: m.LiteralExpr) -> None: ...

    def visit_wildcard_expr(self, expr: m.WildcardExpr) -> None: ...

    def visit_named_type(self, type: m.NamedType) -> None:
        self.wrap(type, "named-type")

    def visit_generic_type(self, type: m.GenericType) -> None:
        self.wrap(type, "generic-type")
        type.type.accept(self)
        for param in type.params:
            param.accept(self)

    def visit_constraint_type(self, type: m.ConstraintType) -> None:
        self.wrap(type, "constraint-type")
        type.type.accept(self)
        type.constraint.accept(self)

    def visit_complex_type(self, type: m.ComplexType) -> None:
        self.wrap(type, "complex-type")
        for prop in type.properties:
            prop.accept(self)


class DiagnosticsHighlighter(Highlighter):
    EXTRA_CSS_PATH: Optional[Path] = Path(__file__).parent / "hl_diagnostic.css"

    def highlight(self, diagnostics: list[Diagnostic]):
        for diagnostic in diagnostics:
            self.wrap(diagnostic, str(diagnostic.type).lower(), diagnostic.message)
