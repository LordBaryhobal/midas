import midas.ast.python as p


class ResolverError(Exception): ...


class Resolver(p.Stmt.Visitor[None], p.Expr.Visitor[None]):
    def __init__(self):
        self.locals: dict[p.Expr, int] = {}
        self.scopes: list[dict[str, bool]] = []

    def resolve(self, *objects: p.Stmt | p.Expr) -> None:
        for obj in objects:
            obj.accept(self)

    def begin_scope(self):
        self.scopes.append({})

    def end_scope(self):
        self.scopes.pop()

    def declare(self, name: str) -> None:
        if len(self.scopes) == 0:
            return
        scope: dict[str, bool] = self.scopes[-1]
        if name in scope:
            raise ResolverError(
                f"A variable with the name {name} is already declared in this scope"
            )
        scope[name] = False

    def define(self, name: str) -> None:
        if len(self.scopes) == 0:
            return
        self.scopes[-1][name] = True

    def resolve_local(self, expr: p.Expr, name: str) -> None:
        for i, scope in enumerate(reversed(self.scopes)):
            if name in scope:
                self.locals[expr] = i
                return

    def resolve_function(self, function: p.Function) -> None:
        self.begin_scope()
        for param in function.all_args:
            self.declare(param.name)
            self.define(param.name)
        self.resolve(*function.body)
        self.end_scope()

    def visit_expression_stmt(self, stmt: p.ExpressionStmt) -> None:
        stmt.expr.accept(self)

    def visit_function(self, stmt: p.Function) -> None:
        # Declare before resolving body to allow recursion
        self.declare(stmt.name)
        self.define(stmt.name)
        self.resolve_function(stmt)

    def visit_type_assign(self, stmt: p.TypeAssign) -> None:
        self.declare(stmt.name)
        # NOTE: resolve type here?
        self.define(stmt.name)

    def visit_assign_stmt(self, stmt: p.AssignStmt) -> None:
        self.resolve(stmt.value)
        for target in stmt.targets:
            match target:
                case p.VariableExpr(name=name):
                    self.resolve_local(target, name)
                    # TODO: declare if not found
                case _:
                    raise Exception(f"Unsupported assignment to {target}")

    def visit_return_stmt(self, stmt: p.ReturnStmt) -> None:
        if stmt.value is not None:
            self.resolve(stmt.value)

    def visit_binary_expr(self, expr: p.BinaryExpr) -> None:
        self.resolve(expr.left)
        self.resolve(expr.right)

    def visit_compare_expr(self, expr: p.CompareExpr) -> None:
        self.resolve(expr.left)
        self.resolve(expr.right)

    def visit_unary_expr(self, expr: p.UnaryExpr) -> None:
        self.resolve(expr.right)

    def visit_call_expr(self, expr: p.CallExpr) -> None:
        self.resolve(expr.callee)
        for arg in expr.arguments:
            self.resolve(arg)
        for arg in expr.keywords.values():
            self.resolve(arg)

    def visit_get_expr(self, expr: p.GetExpr) -> None:
        self.resolve(expr.object)

    def visit_literal_expr(self, expr: p.LiteralExpr) -> None:
        pass

    def visit_variable_expr(self, expr: p.VariableExpr) -> None:
        if len(self.scopes) != 0 and self.scopes[-1].get(expr.name) is False:
            raise ResolverError(
                f"Cannot use local variable '{expr.name}' in its own initializer"
            )  # aka. UnboundLocalError
        self.resolve_local(expr, expr.name)

    def visit_logical_expr(self, expr: p.LogicalExpr) -> None:
        self.resolve(expr.left)
        self.resolve(expr.right)

    def visit_set_expr(self, expr: p.SetExpr) -> None:
        self.resolve(expr.value)
        self.resolve(expr.object)

    def visit_cast_expr(self, expr: p.CastExpr) -> None:
        self.resolve(expr.expr)
