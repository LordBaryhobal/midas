from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Generic, Optional, Protocol, TextIO, TypeVar

from midas.ast.location import Location
import midas.ast.midas as m
import midas.ast.python as p

H = TypeVar("H", bound="Highlighter", contravariant=True)


class Highlightable(Protocol, Generic[H]):
    def accept(self, visitor: H): ...


class Locatable(Protocol):
    @property
    @abstractmethod
    def location(self) -> Optional[Location]: ...


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

    def wrap(self, node: Locatable, cls: str):
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
        self.openings.setdefault(start_pos, []).append(opening)
        self.closings.setdefault(end_pos, []).insert(0, closing)
        if start_pos[0] != end_pos[0]:
            for l in range(start_pos[0], end_pos[0]):
                c: int = len(self.lines[l - 1])
                self.closings.setdefault((l, c), []).insert(0, closing)
                self.openings.setdefault((l + 1, 0), []).append(opening)


class PythonHighlighter(Highlighter, p.Expr.Visitor[None]):
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

    def visit_function(self, node: p.Function) -> None:
        self.wrap(node, "function")
        for arg in node.posonlyargs + node.args + node.kwonlyargs:
            arg.accept(self)

    def visit_function_argument(self, node: p.FunctionArgument) -> None:
        self.wrap(node, "argument")
        if node.type is not None:
            node.type.accept(self)


class MidasHighlighter(Highlighter, m.Stmt.Visitor[None], m.Expr.Visitor[None]):
    EXTRA_CSS_PATH: Optional[Path] = Path(__file__).parent / "hl_midas.css"

    def highlight(self, node: Highlightable[MidasHighlighter]):
        node.accept(self)

    def visit_simple_type_stmt(self, stmt: m.SimpleTypeStmt) -> None:
        self.wrap(stmt, "simple-type")
        if stmt.template is not None:
            stmt.template.accept(self)
        stmt.base.accept(self)
        if stmt.constraint is not None:
            self.wrap(stmt.constraint, "constraint")
            stmt.constraint.accept(self)

    def visit_complex_type_stmt(self, stmt: m.ComplexTypeStmt) -> None:
        self.wrap(stmt, "complex-type")
        if stmt.template is not None:
            stmt.template.accept(self)
        for prop in stmt.properties:
            prop.accept(self)

    def visit_property_stmt(self, stmt: m.PropertyStmt) -> None:
        self.wrap(stmt, "property")
        stmt.type.accept(self)
        if stmt.constraint is not None:
            self.wrap(stmt.constraint, "constraint")
            stmt.constraint.accept(self)

    def visit_extend_stmt(self, stmt: m.ExtendStmt) -> None:
        self.wrap(stmt, "extend")
        stmt.type.accept(self)
        for op in stmt.operations:
            op.accept(self)

    def visit_op_stmt(self, stmt: m.OpStmt) -> None:
        self.wrap(stmt, "op")
        stmt.operand.accept(self)
        stmt.result.accept(self)

    def visit_predicate_stmt(self, stmt: m.PredicateStmt) -> None:
        self.wrap(stmt, "predicate")
        stmt.type.accept(self)
        stmt.condition.accept(self)

    def visit_simple_type_expr(self, expr: m.SimpleTypeExpr) -> None:
        self.wrap(expr, "simple-type-expr")

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

    def visit_template_expr(self, expr: m.TemplateExpr) -> None:
        self.wrap(expr, "template")
        expr.type.accept(self)

    def visit_type_expr(self, expr: m.TypeExpr) -> None:
        self.wrap(expr, "type")
        if expr.template is not None:
            expr.template.accept(self)
