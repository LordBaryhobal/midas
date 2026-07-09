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
    DictExpr,
    Expr,
    ExpressionStmt,
    ForStmt,
    FrameColumn,
    FrameType,
    FromImportStmt,
    Function,
    GetExpr,
    IfStmt,
    ImportAlias,
    ImportStmt,
    ListExpr,
    LiteralExpr,
    LogicalExpr,
    MidasType,
    ParamSpec,
    RawExpr,
    RawStmt,
    ReturnStmt,
    SliceExpr,
    Stmt,
    SubscriptExpr,
    TernaryExpr,
    TupleExpr,
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
    """A parser to convert raw Python `ast` nodes in custom IR nodes"""

    CAST_FUNCTION = "cast"
    UNSAFE_CAST_FUNCTION = "unsafe_cast"

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

            case ast.For(orelse=[]):
                return self.parse_for(node)

            case ast.Import(names=imports):
                return ImportStmt(
                    location=location,
                    imports=self._parse_imports(imports),
                )

            case ast.ImportFrom(module=module, names=imports, level=level):
                return FromImportStmt(
                    location=location,
                    module=module,
                    imports=self._parse_imports(imports),
                    level=level,
                )

            case _:
                print(f"Unsupported statement: {ast.unparse(node)}")
                return RawStmt(location=location, stmt=node)

    def _parse_imports(self, imports: list[ast.alias]) -> list[ImportAlias]:
        return [
            ImportAlias(
                location=Location.from_ast(import_),
                name=import_.name,
                alias=import_.asname,
            )
            for import_ in imports
        ]

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

    def parse_for(self, node: ast.For) -> ForStmt:
        body: list[Stmt] = []
        for stmt in node.body:
            stmts = self.parse_stmt(stmt)
            if isinstance(stmts, Stmt):
                body.append(stmts)
            elif stmts is not None:
                body.extend(stmts)

        return ForStmt(
            location=Location.from_ast(node),
            target=self.parse_expr(node.target),
            iterator=self.parse_expr(node.iter),
            body=body,
        )

    def parse_function(self, node: ast.FunctionDef) -> Function:
        loc: Location = Location.from_ast(node)
        match node:
            case ast.FunctionDef(
                name=name,
                args=args,
                returns=returns,
                body=raw_body,
            ):
                body: list[Stmt] = []
                for stmt in raw_body:
                    stmts = self.parse_stmt(stmt)
                    if isinstance(stmts, Stmt):
                        body.append(stmts)
                    elif stmts is not None:
                        body.extend(stmts)

                return Function(
                    location=loc,
                    name=name,
                    params=self._parse_param_spec(args),
                    returns=self._parse_type(returns) if returns is not None else None,
                    body=body,
                )
            case _:
                print(f"Unsupported function definition: {ast.unparse(node)}")

    def _parse_param_spec(self, args: ast.arguments) -> ParamSpec:
        def parse_params(
            args_list: list[ast.arg], defaults: list[Optional[Expr]]
        ) -> list[Function.Parameter]:
            return [
                self._parse_function_parameter(arg, default)
                for arg, default in zip(args_list, defaults)
            ]

        defaults: list[ast.expr] = args.defaults
        parsed_defaults: list[Optional[Expr]] = [
            self.parse_expr(default) for default in defaults
        ]
        n_pos: int = len(args.posonlyargs)
        n_mixed: int = len(args.args)
        n_all_pos = n_pos + n_mixed
        parsed_defaults = [
            None,
        ] * (n_all_pos - len(defaults)) + parsed_defaults

        pos_defaults: list[Optional[Expr]] = parsed_defaults[:n_pos]
        mixed_defaults: list[Optional[Expr]] = parsed_defaults[n_pos:]
        kw_defaults: list[Optional[Expr]] = [
            self.parse_expr(default) if default is not None else None
            for default in args.kw_defaults
        ]

        return ParamSpec(
            pos=parse_params(args.posonlyargs, pos_defaults),
            mixed=parse_params(args.args, mixed_defaults),
            kw=parse_params(args.kwonlyargs, kw_defaults),
        )

    def _parse_function_parameter(
        self, arg: ast.arg, default: Optional[Expr]
    ) -> Function.Parameter:
        loc: Location = Location.from_ast(arg)
        name: str = arg.arg
        type: Optional[MidasType] = None
        if arg.annotation is not None:
            type = self._parse_type(arg.annotation)
        return Function.Parameter(
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

            case ast.Subscript(value=ast.Name(id=name), slice=arg):
                args: tuple[MidasType, ...] = (
                    tuple(self._parse_type(a) for a in arg.elts)
                    if isinstance(arg, ast.Tuple)
                    else (self._parse_type(arg),)
                )
                return BaseType(
                    location=loc,
                    base=name,
                    args=args,
                )

            case ast.Name(id=name):
                return BaseType(
                    location=loc,
                    base=name,
                    args=(),
                )

            case ast.Constant(value=None):
                return BaseType(
                    location=loc,
                    base="None",
                    args=(),
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

            case ast.Slice() | ast.Name() | ast.Subscript():
                columns.append(self._parse_frame_column(schema))

            case _:
                raise UnsupportedSyntaxError(schema)

        return FrameType(location=loc, columns=columns)

    def _parse_frame_column(self, column: ast.expr) -> FrameColumn:
        loc: Location = Location.from_ast(column)
        match column:
            case ast.Name() | ast.Subscript():
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

            case ast.Call(func=ast.Name(id=self.UNSAFE_CAST_FUNCTION)):
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

            case ast.Dict(keys=keys, values=values):
                return DictExpr(
                    location=location,
                    keys=[
                        self.parse_expr(key) if key is not None else None
                        for key in keys
                    ],
                    values=[self.parse_expr(value) for value in values],
                )

            case ast.Subscript(value=value, slice=index):
                return SubscriptExpr(
                    location=location,
                    object=self.parse_expr(value),
                    index=self.parse_expr(index),
                )

            case ast.Slice(lower=lower, upper=upper, step=step):
                return SliceExpr(
                    location=location,
                    lower=self.parse_expr(lower) if lower is not None else None,
                    upper=self.parse_expr(upper) if upper is not None else None,
                    step=self.parse_expr(step) if step is not None else None,
                )

            case ast.Tuple(elts=items):
                return TupleExpr(
                    location=location,
                    items=tuple(self.parse_expr(item) for item in items),
                )

            case _:
                print(f"Unsupported expression: {ast.unparse(node)}")
                return RawExpr(location=location, expr=node)

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
        assert isinstance(node.func, ast.Name)
        func: str = node.func.id
        match node:
            case ast.Call(args=[type, expr], keywords=[]):
                return CastExpr(
                    location=Location.from_ast(node),
                    type=self._parse_type(type),
                    expr=self.parse_expr(expr),
                    unsafe=func == self.UNSAFE_CAST_FUNCTION,
                )
            case _:
                raise InvalidSyntaxError(
                    f"Invalid call to {func}, expected type and expression"
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
