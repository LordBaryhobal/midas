from pathlib import Path
from typing import TextIO

from midas.ast.python import (
    BaseType,
    ConstraintType,
    Expr,
    FrameColumn,
    FrameType,
    Function,
    FunctionArgument,
)


class PythonHighlighter(Expr.Visitor[None]):
    CSS_PATH: Path = Path(__file__).parent / "highlight.css"

    def __init__(self, source: str) -> None:
        self.source: str = source
        self.lines: list[str] = self.source.splitlines()
        self.openings: dict[tuple[int, int], list[str]] = {}
        self.closings: dict[tuple[int, int], list[str]] = {}

    def highlight(self, node: Expr):
        node.accept(self)

    def dump(self, buf: TextIO):
        css: str = self.CSS_PATH.read_text()
        css = "\n".join(("        " + line).rstrip() for line in css.splitlines())
        lines: list[str] = [
            "<!DOCTYPE html>",
            '<html lang="en">',
            "<head>",
            '    <meta charset="UTF-8">',
            '    <meta name="viewport" content="width=device-width, initial-scale=1.0">',
            "    <title>Highlighted file</title>",
            "    <style>",
            css,
            "    </style>",
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

    def wrap(self, node: Expr, cls: str):
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

    def visit_base_type(self, node: BaseType) -> None:
        self.wrap(node, "base-type")
        if node.param is not None:
            self.wrap(node.param, "param")
            node.param.accept(self)

    def visit_constraint_type(self, node: ConstraintType) -> None:
        self.wrap(node, "constraint-type")
        node.type.accept(self)

    def visit_frame_column(self, node: FrameColumn) -> None:
        self.wrap(node, "frame-column")
        if node.type is not None:
            node.type.accept(self)

    def visit_frame_type(self, node: FrameType) -> None:
        self.wrap(node, "frame-type")
        for column in node.columns:
            column.accept(self)

    def visit_function(self, node: Function) -> None:
        self.wrap(node, "function")
        for arg in node.posonlyargs + node.args + node.kwonlyargs:
            arg.accept(self)

    def visit_function_argument(self, node: FunctionArgument) -> None:
        self.wrap(node, "argument")
        if node.type is not None:
            node.type.accept(self)
