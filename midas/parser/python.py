import ast
from typing import Any, Optional

from midas.ast.python import (
    BaseType,
    ConstraintType,
    FrameColumn,
    FrameType,
    Function,
    FunctionArgument,
    MidasType,
)


class InvalidSyntaxError(Exception):
    pass


class UnsupportedSyntaxError(Exception):
    def __init__(self, expr: ast.expr) -> None:
        super().__init__(
            f"Unsupported syntax at L{expr.lineno}:{expr.col_offset}: {ast.unparse(expr)}"
        )


class PythonParser(ast.NodeVisitor):
    def __init__(self) -> None:
        super().__init__()

        self.annotations: list[tuple[str, Optional[MidasType]]] = []
        self.functions: list[Function] = []

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

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        self.functions.append(self._parse_function(node))

        # Call visit on children to process body
        # TODO: scope the resulting nodes to the function
        self.generic_visit(node)

    def _parse_function(self, node: ast.FunctionDef) -> Function:
        match node:
            case ast.FunctionDef(
                name=name,
                args=ast.arguments(
                    posonlyargs=posonlyargs,
                    args=args,
                    kwonlyargs=kwonlyargs,
                ),
                returns=returns,
            ):

                def parse_args(args_list: list[ast.arg]) -> list[FunctionArgument]:
                    return [self._parse_function_argument(arg) for arg in args_list]

                return Function(
                    name=name,
                    posonlyargs=parse_args(posonlyargs),
                    args=parse_args(args),
                    kwonlyargs=parse_args(kwonlyargs),
                    returns=self._parse_type(returns) if returns is not None else None,
                )

    def _parse_function_argument(self, arg: ast.arg) -> FunctionArgument:
        name: str = arg.arg
        type: Optional[MidasType] = None
        if arg.annotation is not None:
            type = self._parse_type(arg.annotation)
        return FunctionArgument(name=name, type=type)

    def _parse_type(
        self, type_expr: ast.expr, root: bool = False
    ) -> Optional[MidasType]:
        match type_expr:
            case ast.Subscript(value=ast.Name(id="Frame"), slice=schema):
                return self._parse_frame_type(schema)

            case ast.Subscript(value=ast.Name(id=name), slice=param):
                return BaseType(base=name, param=self._parse_type(param))

            case ast.Name(id=name):
                return BaseType(base=name, param=None)

            case ast.BinOp(left=left_expr, op=ast.Add(), right=right_expr):
                left = self._parse_type(left_expr)
                match left:
                    case None:
                        raise InvalidSyntaxError()

                    # If chained constraints, separate base type and rebuild constraint
                    case ConstraintType(type=left_type, constraint=left_constraint):
                        constraint = ast.BinOp(
                            left=left_constraint,
                            op=ast.Add(),
                            right=right_expr,
                        )
                        ast.copy_location(constraint, type_expr)
                        return ConstraintType(
                            type=left_type,
                            constraint=constraint,
                        )

                    case _:
                        return ConstraintType(type=left, constraint=right_expr)

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
