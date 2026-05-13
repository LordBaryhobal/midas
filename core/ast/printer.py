from contextlib import contextmanager
from enum import Enum, auto
import io
from typing import Generator, Optional

from core.ast.annotations import Expr, TypeExpr, SchemaExpr, SchemaElementExpr


class _Level(Enum):
    EMPTY = auto()
    ACTIVE = auto()
    LAST = auto()


class AnnotationAstPrinter(Expr.Visitor[None]):
    LAST_CHILD = "└── "
    CHILD = "├── "
    VERTICAL = "│   "
    EMPTY = "    "

    def __init__(self):
        self._levels: list[_Level] = []
        self._idx: Optional[int] = None
        self._buf: io.StringIO = io.StringIO()

    def print(self, expr: Expr):
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

    def _write_line(self, text: str):
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
        self, label: str, child: Optional[Expr], *, last: bool = False
    ):
        if last:
            self._mark_last()
        if child is None:
            self._write_line(f"{label}: None")
        else:
            self._write_line(label)
            with self._child_level(last=True):
                child.accept(self)

    def visit_type_expr(self, expr: TypeExpr):
        self._write_line("TypeExpr")
        with self._child_level():
            self._write_line(f'name: "{expr.name.lexeme}"')
            self._write_optional_child("schema", expr.schema, last=True)

    def visit_schema_expr(self, expr: SchemaExpr):
        self._write_line("SchemaExpr")
        with self._child_level():
            for i, elmt in enumerate(expr.elements):
                self._idx = i
                if i == len(expr.elements) - 1:
                    self._mark_last()
                elmt.accept(self)

    def visit_schema_element_expr(self, expr: SchemaElementExpr):
        self._write_line("SchemaElementExpr")
        with self._child_level():
            name_text: str = "None" if expr.name is None else f'"{expr.name.lexeme}"'
            self._write_line(f"name: {name_text}")
            self._write_optional_child("type", expr.type, last=True)


class AnnotationPrinter(Expr.Visitor[str]):
    def print(self, expr: Expr):
        return expr.accept(self)

    def visit_type_expr(self, expr: TypeExpr) -> str:
        schema: str = ""
        if expr.schema is not None:
            schema = expr.schema.accept(self)
        return f"{expr.name.lexeme}{schema}"

    def visit_schema_expr(self, expr: SchemaExpr) -> str:
        res: str = expr.left.lexeme
        res += ", ".join(elmt.accept(self) for elmt in expr.elements)
        res += expr.right.lexeme
        return res

    def visit_schema_element_expr(self, expr: SchemaElementExpr) -> str:
        parts: list[str] = []
        if expr.name is not None:
            parts.append(expr.name.lexeme)

        if expr.type is None:
            parts.append("_")
        else:
            parts.append(expr.type.accept(self))
        return ": ".join(parts)
