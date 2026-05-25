import ast
from typing import Optional

from midas.ast.location import Location

from midas.ast.python import (
    AssignStmt,
    BaseType,
    ConstraintType,
    Expr,
    FrameColumn,
    FrameType,
    Function,
    MidasType,
    Stmt,
    TypeAssign,
    VariableExpr,
)


class InvalidSyntaxError(Exception):
    pass


class UnsupportedSyntaxError(Exception):
    def __init__(self, expr: ast.expr) -> None:
        super().__init__(
            f"Unsupported syntax at L{expr.lineno}:{expr.col_offset}: {ast.unparse(expr)}"
        )


class PythonParser:
    def parse_module(self, node: ast.Module) -> list[Stmt]:
        statements: list[Stmt] = []
        for stmt in node.body:
            parsed: None | Stmt | list[Stmt] = self.parse_stmt(stmt)
            if isinstance(parsed, Stmt):
                statements.append(parsed)
            elif parsed is not None:
                statements.extend(parsed)
        return statements

    def parse_stmt(self, node: ast.stmt) -> None | Stmt | list[Stmt]:
        match node:
            case ast.AnnAssign():
                return self.parse_annotation_assign(node)

            case ast.Assign():
                return self.parse_assign(node)

            case ast.FunctionDef():
                return self.parse_function(node)

            case _:
                print(f"Unsupported statement: {ast.unparse(node)}")
                return None

    def parse_annotation_assign(self, node: ast.AnnAssign) -> list[Stmt]:
        statements: list[Stmt] = []
        loc: Location = Location.from_ast(node)
        match node:
            case ast.AnnAssign(
                target=ast.Name(id=target),
                annotation=annotation,
                value=value,
                simple=1,
            ):
                type = self._parse_type(annotation, root=True)
                if type is not None:
                    statements.append(
                        TypeAssign(
                            location=loc,
                            name=target,
                            type=type,
                        )
                    )

                if value is not None:
                    statements.append(
                        AssignStmt(
                            location=loc,
                            targets=[
                                VariableExpr(
                                    location=Location.from_ast(node.target), name=target
                                ),
                            ],
                            value=self.parse_expr(value),
                        ),
                    )
            case _:
                print(f"Unsupported annotation: {ast.unparse(node)}")
        return statements

    def parse_assign(self, node: ast.Assign) -> AssignStmt:
        targets: list[Expr] = []
        for target in node.targets:
            targets.append(self.parse_expr(target))
        value: Expr = self.parse_expr(node.value)
        return AssignStmt(
            location=Location.from_ast(node),
            targets=targets,
            value=value,
        )

    def parse_function(self, node: ast.FunctionDef) -> Function:
        loc: Location = Location.from_ast(node)
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

                def parse_args(args_list: list[ast.arg]) -> list[Function.Argument]:
                    return [self._parse_function_argument(arg) for arg in args_list]

                return Function(
                    location=loc,
                    name=name,
                    posonlyargs=parse_args(posonlyargs),
                    args=parse_args(args),
                    kwonlyargs=parse_args(kwonlyargs),
                    returns=self._parse_type(returns) if returns is not None else None,
                )
            case _:
                print(f"Unsupported function definition: {ast.unparse(node)}")

    def _parse_function_argument(self, arg: ast.arg) -> Function.Argument:
        loc: Location = Location.from_ast(arg)
        name: str = arg.arg
        type: Optional[MidasType] = None
        if arg.annotation is not None:
            type = self._parse_type(arg.annotation)
        return Function.Argument(
            location=loc,
            name=name,
            type=type,
        )

    def _parse_type(
        self, type_expr: ast.expr, root: bool = False
    ) -> Optional[MidasType]:
        loc: Location = Location.from_ast(type_expr)
        match type_expr:
            case ast.Subscript(value=ast.Name(id="Frame"), slice=schema):
                return self._parse_frame_type(schema)

            case ast.Subscript(value=ast.Name(id=name), slice=param):
                return BaseType(
                    location=loc,
                    base=name,
                    param=self._parse_type(param),
                )

            case ast.Name(id=name):
                return BaseType(
                    location=loc,
                    base=name,
                    param=None,
                )

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
                            location=loc,
                            type=left_type,
                            constraint=constraint,
                        )

                    case _:
                        return ConstraintType(
                            location=loc,
                            type=left,
                            constraint=right_expr,
                        )

            case _:
                if root:
                    return None
                raise UnsupportedSyntaxError(type_expr)

    def _parse_frame_type(self, schema: ast.expr) -> FrameType:
        loc: Location = Location.from_ast(schema)
        columns: list[FrameColumn] = []

        match schema:
            case ast.Tuple(elts=cols):
                for col in cols:
                    columns.append(self._parse_frame_column(col))

            case ast.Slice() | ast.Name():
                columns.append(self._parse_frame_column(schema))

            case _:
                raise UnsupportedSyntaxError(schema)

        return FrameType(location=loc, columns=columns)

    def _parse_frame_column(self, column: ast.expr) -> FrameColumn:
        loc: Location = Location.from_ast(column)
        match column:
            case ast.Name():
                return FrameColumn(
                    location=loc,
                    name=None,
                    type=self._parse_type(column),
                )

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
                return FrameColumn(location=loc, name=name, type=type)

            case _:
                raise UnsupportedSyntaxError(column)

    def parse_expr(self, node: ast.expr) -> Expr:
        raise NotImplementedError()
