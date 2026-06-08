import ast
from typing import Optional

from midas.ast.location import Location
from midas.ast.python import (
    AssignStmt,
    BaseType,
    BinaryExpr,
    CallExpr,
    CastExpr,
    CompareExpr,
    ConstraintType,
    Expr,
    ExpressionStmt,
    FrameColumn,
    FrameType,
    Function,
    GetExpr,
    IfStmt,
    ListExpr,
    LiteralExpr,
    LogicalExpr,
    MidasType,
    ReturnStmt,
    Stmt,
    TernaryExpr,
    TypeAssign,
    UnaryExpr,
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
    CAST_FUNCTION = "cast"

    def parse_module(self, node: ast.Module) -> list[Stmt]:
        statements: list[Stmt] = []
        for stmt in node.body:
            try:
                parsed: None | Stmt | list[Stmt] = self.parse_stmt(stmt)
                if isinstance(parsed, Stmt):
                    statements.append(parsed)
                elif parsed is not None:
                    statements.extend(parsed)
            except UnsupportedSyntaxError as e:
                print(f"{e}, skipping")
                continue
        return statements

    def parse_stmt(self, node: ast.stmt) -> None | Stmt | list[Stmt]:
        location: Location = Location.from_ast(node)
        match node:
            case ast.AnnAssign():
                return self.parse_annotation_assign(node)

            case ast.Assign():
                return self.parse_assign(node)

            case ast.AugAssign():
                return self.parse_aug_assign(node)

            case ast.FunctionDef():
                return self.parse_function(node)

            case ast.Expr(value=expr):
                return ExpressionStmt(
                    location=location,
                    expr=self.parse_expr(expr),
                )

            case ast.Return(value=value):
                return ReturnStmt(
                    location=location,
                    value=self.parse_expr(value) if value is not None else None,
                )

            case ast.If():
                return self.parse_if(node)

            case ast.Pass():
                return None

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
                type = self._parse_type(annotation)
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

    def parse_aug_assign(self, node: ast.AugAssign) -> AssignStmt:
        location: Location = Location.from_ast(node)
        target: Expr = self.parse_expr(node.target)
        value: Expr = self.parse_expr(node.value)
        return AssignStmt(
            location=location,
            targets=[target],
            value=BinaryExpr(
                location=location,
                left=target,
                operator=node.op,
                right=value,
            ),
        )

    def parse_if(self, node: ast.If) -> IfStmt:
        body: list[Stmt] = []
        for stmt in node.body:
            stmts = self.parse_stmt(stmt)
            if isinstance(stmts, Stmt):
                body.append(stmts)
            elif stmts is not None:
                body.extend(stmts)

        orelse: list[Stmt] = []
        for stmt in node.orelse:
            stmts = self.parse_stmt(stmt)
            if isinstance(stmts, Stmt):
                orelse.append(stmts)
            elif stmts is not None:
                orelse.extend(stmts)

        return IfStmt(
            location=Location.from_ast(node),
            test=self.parse_expr(node.test),
            body=body,
            orelse=orelse,
        )

    def parse_function(self, node: ast.FunctionDef) -> Function:
        loc: Location = Location.from_ast(node)
        match node:
            case ast.FunctionDef(
                name=name,
                args=ast.arguments(
                    posonlyargs=posonlyargs,
                    args=args,
                    vararg=sink,
                    kwonlyargs=kwonlyargs,
                    kwarg=kw_sink,
                    defaults=defaults,
                    kw_defaults=kw_defaults,
                ),
                returns=returns,
                body=raw_body,
            ):

                def parse_args(
                    args_list: list[ast.arg], defaults: list[Optional[Expr]]
                ) -> list[Function.Argument]:
                    return [
                        self._parse_function_argument(arg, default)
                        for arg, default in zip(args_list, defaults)
                    ]

                body: list[Stmt] = []
                for stmt in raw_body:
                    stmts = self.parse_stmt(stmt)
                    if isinstance(stmts, Stmt):
                        body.append(stmts)
                    elif stmts is not None:
                        body.extend(stmts)

                parsed_defaults: list[Optional[Expr]] = [
                    self.parse_expr(default) for default in defaults
                ]
                n_posargs: int = len(posonlyargs)
                n_args: int = len(args)
                n_all_posargs = n_posargs + n_args
                parsed_defaults = [
                    None,
                ] * (n_all_posargs - len(defaults)) + parsed_defaults

                posargs_defaults: list[Optional[Expr]] = parsed_defaults[:n_posargs]
                args_defaults: list[Optional[Expr]] = parsed_defaults[n_posargs:]
                kwargs_defaults: list[Optional[Expr]] = [
                    self.parse_expr(default) if default is not None else None
                    for default in kw_defaults
                ]

                return Function(
                    location=loc,
                    name=name,
                    posonlyargs=parse_args(posonlyargs, posargs_defaults),
                    args=parse_args(args, args_defaults),
                    sink=(
                        self._parse_function_argument(sink, None)
                        if sink is not None
                        else None
                    ),
                    kwonlyargs=parse_args(kwonlyargs, kwargs_defaults),
                    kw_sink=(
                        self._parse_function_argument(kw_sink, None)
                        if kw_sink is not None
                        else None
                    ),
                    returns=self._parse_type(returns) if returns is not None else None,
                    body=body,
                )
            case _:
                print(f"Unsupported function definition: {ast.unparse(node)}")

    def _parse_function_argument(
        self, arg: ast.arg, default: Optional[Expr]
    ) -> Function.Argument:
        loc: Location = Location.from_ast(arg)
        name: str = arg.arg
        type: Optional[MidasType] = None
        if arg.annotation is not None:
            type = self._parse_type(arg.annotation)
        return Function.Argument(
            location=loc,
            name=name,
            type=type,
            default=default,
        )

    def _parse_type(self, type_expr: ast.expr) -> MidasType:
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

            case ast.Constant(value=None):
                return BaseType(
                    location=loc,
                    base="None",
                    param=None,
                )

            case _:
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
        location: Location = Location.from_ast(node)
        match node:
            case ast.BoolOp():
                return self.parse_bool_op(node)

            case ast.BinOp(left=left, op=op, right=right):
                return BinaryExpr(
                    location=location,
                    left=self.parse_expr(left),
                    operator=op,
                    right=self.parse_expr(right),
                )

            case ast.UnaryOp(op=op, operand=right):
                return UnaryExpr(
                    location=location,
                    operator=op,
                    right=self.parse_expr(right),
                )

            case ast.Compare():
                return self.parse_compare(node)

            case ast.Call(func=ast.Name(id=self.CAST_FUNCTION)):
                return self.parse_cast(node)

            case ast.Call():
                return self.parse_call(node)

            case ast.IfExp():
                return self.parse_ternary(node)

            case ast.Constant(value=value):
                return LiteralExpr(location=location, value=value)

            case ast.Attribute(value=object, attr=name):
                return GetExpr(
                    location=location,
                    object=self.parse_expr(object),
                    name=name,
                )

            case ast.Name(id=name):
                return VariableExpr(location=location, name=name)

            case ast.List(elts=items):
                return ListExpr(
                    location=location,
                    items=[self.parse_expr(item) for item in items],
                )

            case _:
                raise UnsupportedSyntaxError(node)

    def parse_bool_op(self, node: ast.BoolOp) -> LogicalExpr:
        op: ast.boolop = node.op
        rights: list[Expr] = [self.parse_expr(expr) for expr in node.values]
        expr: LogicalExpr = LogicalExpr(
            location=Location.span(
                rights[0].location,
                rights[1].location,
            ),
            left=rights[0],
            operator=op,
            right=rights[1],
        )
        for right in rights[2:]:
            expr = LogicalExpr(
                location=Location.span(expr.location, right.location),
                left=expr,
                operator=op,
                right=right,
            )
        return expr

    def parse_compare(self, node: ast.Compare) -> Expr:
        ops: list[ast.cmpop] = node.ops
        left: Expr = self.parse_expr(node.left)
        rights: list[Expr] = [self.parse_expr(expr) for expr in node.comparators]
        expr: Expr = CompareExpr(
            location=Location.span(
                left.location,
                rights[0].location,
            ),
            left=left,
            operator=ops[0],
            right=rights[0],
        )
        for i, right in enumerate(rights[1:]):
            comparison = CompareExpr(
                location=Location.span(rights[i].location, right.location),
                left=rights[i],
                operator=ops[i],
                right=right,
            )
            expr = LogicalExpr(
                location=Location.span(expr.location, comparison.location),
                left=expr,
                operator=ast.And(),
                right=comparison,
            )
        return expr

    def parse_cast(self, node: ast.Call) -> CastExpr:
        match node:
            case ast.Call(args=[type, expr], keywords=[]):
                return CastExpr(
                    location=Location.from_ast(node),
                    type=self._parse_type(type),
                    expr=self.parse_expr(expr),
                )
            case _:
                raise InvalidSyntaxError(
                    f"Invalid call to {self.CAST_FUNCTION}, expected type and expression"
                )

    def parse_call(self, node: ast.Call) -> CallExpr:
        return CallExpr(
            location=Location.from_ast(node),
            callee=self.parse_expr(node.func),
            arguments=[self.parse_expr(arg) for arg in node.args],
            keywords={
                arg.arg: self.parse_expr(arg.value)
                for arg in node.keywords
                if arg.arg is not None  # Should always be True, type checker happy
            },
        )

    def parse_ternary(self, node: ast.IfExp) -> TernaryExpr:
        return TernaryExpr(
            location=Location.from_ast(node),
            test=self.parse_expr(node.test),
            if_true=self.parse_expr(node.body),
            if_false=self.parse_expr(node.orelse),
        )
