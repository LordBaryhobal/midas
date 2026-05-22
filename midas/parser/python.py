import ast
from typing import Any, Optional

from midas.ast.python import BaseType, FrameColumn, FrameType, MidasType


class InvalidSyntaxError(Exception):
    pass


class UnsupportedSyntaxError(Exception):
    def __init__(self, expr: ast.expr) -> None:
        super().__init__(f"Unsupported syntax: {ast.unparse(expr)}")


class PythonParser(ast.NodeVisitor):
    def __init__(self) -> None:
        super().__init__()

        self.annotations: list[tuple[str, Optional[MidasType]]] = []

    def visit_AnnAssign(self, node: ast.AnnAssign) -> Any:
        match node:
            case ast.AnnAssign(
                target=ast.Name(id=target), annotation=annotation, simple=1
            ):
                self.annotations.append(
                    (target, self._parse_type(annotation, root=True))
                )

            case _:
                print(f"Unsupported annotation: {ast.unparse(node)}")

    def _parse_type(
        self, type_expr: ast.expr, root: bool = False
    ) -> Optional[MidasType]:
        match type_expr:
            case ast.Subscript(value=ast.Name(id="Frame"), slice=schema):
                return self._parse_frame_type(schema)

            case ast.Subscript(value=ast.Name(id=name), slice=param):
                return BaseType(
                    base=name, param=self._parse_type(param), constraint=None
                )

            case ast.Name(id=name):
                return BaseType(base=name, param=None, constraint=None)

            case ast.BinOp(left=left_expr, op=ast.Add(), right=right_expr):
                print("Constraints not implemented yet")
                return None

            case _:
                if root:
                    return None
                raise UnsupportedSyntaxError(type_expr)

    def _parse_frame_type(self, schema: ast.expr) -> FrameType:
        columns: list[FrameColumn] = []

        match schema:
            case ast.Tuple(elts=cols):
                for col in cols:
                    columns.append(self._parse_frame_column(col))
            case ast.Slice() | ast.Name():
                columns.append(self._parse_frame_column(schema))
            case _:
                raise UnsupportedSyntaxError(schema)

        return FrameType(columns=columns)

    def _parse_frame_column(self, column: ast.expr) -> FrameColumn:
        match column:
            case ast.Name():
                return FrameColumn(name=None, type=self._parse_type(column))
            case ast.Slice(lower=ast.Name(id=name), upper=type_expr):
                if name == "_":
                    name = None

                type: Optional[MidasType] = None
                match type_expr:
                    case None:
                        raise InvalidSyntaxError("Missing column type")
                    case ast.Name(id="_"):
                        type = None
                    case ast.expr():
                        type = self._parse_type(type_expr)
                    case _:
                        raise UnsupportedSyntaxError(type_expr)
                return FrameColumn(name=name, type=type)
            case _:
                raise UnsupportedSyntaxError(column)
