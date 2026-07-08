import midas.ast.python as p
from midas.ast.location import Location
from midas.checker.reporter import FileReporter


class ResolverError(Exception): ...


class Resolver(p.Stmt.Visitor[None], p.Expr.Visitor[None]):
    """A variable assignment and reference resolver

    This class keeps track of which scope a variable is defined in and which
    scope is referred to when a variable is referenced
    """

    def __init__(self, reporter: FileReporter):
        self.locals: dict[p.Expr, int] = {}
        self.scopes: list[dict[str, bool]] = [{}]
        self.reporter: FileReporter = reporter

    def resolve(self, *objects: p.Stmt | p.Expr) -> None:
        """Resolve the given statements or expressions"""

        for obj in objects:
            obj.accept(self)

    def begin_scope(self):
        """Begin a new scope inside the current one"""
        self.scopes.append({})

    def end_scope(self) -> dict[str, bool]:
        """Close and return the current scope"""
        return self.scopes.pop()

    def declare(self, location: Location, name: str) -> None:
        """Declare a variable in the current scope

        This method must be called *before* evaluating the variable initializer

        Args:
            name (str): the name of the variable
        """
        if len(self.scopes) == 0:
            return
        scope: dict[str, bool] = self.scopes[-1]
        if name in scope:
            self.reporter.error(
                location,
                f"A variable with the name '{name}' is already declared in this scope",
            )
        else:
            scope[name] = False

    def define(self, name: str) -> None:
        """Define a variable in the current scope

        This method must be called *after* evaluating the variable initializer

        Args:
            name (str): the name of the variable
        """
        if len(self.scopes) == 0:
            return
        self.scopes[-1][name] = True

    def resolve_local(self, expr: p.Expr, name: str) -> None:
        """Resolve a variable reference and store the scope distance

        This method associates to the variable expression a number representing
        the "distance" of the variable declaration, i.e. the number of scope
        levels to go "up" to find the closest declaration for that variable.

        Args:
            expr (p.Expr): the variable expression
            name (str): the name of the variable
        """
        for i, scope in enumerate(reversed(self.scopes)):
            if name in scope:
                self.locals[expr] = i
                return

    def is_declared(self, name: str) -> bool:
        """Check whether the given variable is defined in any scope

        Args:
            name (str): the name of the variable

        Returns:
            bool: `True` if the variable is defined in a scope, `False` otherwise
        """
        for scope in self.scopes:
            if name in scope:
                return True
        return False

    def resolve_function(self, function: p.Function) -> None:
        """Resolve a function definition

        This method creates a new scope for the function, resolves all the
        parameter declarations and then the body.

        Args:
            function (p.Function): the function to resolve
        """
        self.begin_scope()
        for param in function.params.all:
            if param.default is not None:
                self.resolve(param.default)

        for param in function.params.all:
            self.declare(function.location, param.name)
            self.define(param.name)
        self.resolve(*function.body)
        self.end_scope()

    def visit_expression_stmt(self, stmt: p.ExpressionStmt) -> None:
        stmt.expr.accept(self)

    def visit_function(self, stmt: p.Function) -> None:
        # Declare before resolving body to allow recursion
        self.declare(stmt.location, stmt.name)
        self.define(stmt.name)
        self.resolve_function(stmt)

    def visit_type_assign(self, stmt: p.TypeAssign) -> None:
        self.declare(stmt.location, stmt.name)

    def visit_assign_stmt(self, stmt: p.AssignStmt) -> None:
        self.resolve(stmt.value)
        for target in stmt.targets:
            self._visit_assign(target)

    def _visit_assign(self, target: p.Expr):
        match target:
            case p.VariableExpr(name=name):
                if not self.is_declared(name):
                    self.declare(target.location, name)
                self.define(name)
                target.accept(self)

            case p.GetExpr():
                target.accept(self)

            case p.SubscriptExpr():
                target.accept(self)

            case _:
                self.reporter.error(
                    target.location, f"Unsupported assignment to {target}"
                )

    def visit_return_stmt(self, stmt: p.ReturnStmt) -> None:
        if stmt.value is not None:
            self.resolve(stmt.value)

    def visit_if_stmt(self, stmt: p.IfStmt) -> None:
        # Not resolved in sub-environment because assignments in the test leak out of the if
        # For example:
        # if (m := 1 + 1) < 2:
        #     ...
        # print(m)  # <- m is still defined
        self.resolve(stmt.test)

        # Body
        self.begin_scope()
        self.resolve(*stmt.body)
        body: dict[str, bool] = self.end_scope()

        # Else
        self.begin_scope()
        self.resolve(*stmt.orelse)
        else_: dict[str, bool] = self.end_scope()

        # Define variables in this scope if it was defined in both body and else blocks
        for name, is_defined in body.items():
            if is_defined and else_.get(name, False):
                self.define(name)

    def visit_pass(self, stmt: p.Pass) -> None:
        pass

    def visit_for_stmt(self, stmt: p.ForStmt) -> None:
        self.resolve(stmt.iterator)
        self._visit_assign(stmt.target)
        self.begin_scope()
        self.resolve(*stmt.body)
        self.end_scope()

    def visit_import_stmt(self, stmt: p.ImportStmt) -> None:
        self._resolve_imports(stmt.imports)

    def visit_from_import_stmt(self, stmt: p.FromImportStmt) -> None:
        self._resolve_imports(stmt.imports)

    def _resolve_imports(self, imports: list[p.ImportAlias]) -> None:
        for import_ in imports:
            name: str = import_.imported_name
            self.declare(import_.location, name)
            self.define(name)

    def visit_raw_stmt(self, stmt: p.RawStmt) -> None:
        pass

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
            self.reporter.error(
                expr.location,
                f"Variable '{expr.name}' is declared but may not be defined",
            )  # aka. UnboundLocalError
        self.resolve_local(expr, expr.name)

    def visit_logical_expr(self, expr: p.LogicalExpr) -> None:
        self.resolve(expr.left)
        self.resolve(expr.right)

    def visit_cast_expr(self, expr: p.CastExpr) -> None:
        self.resolve(expr.expr)

    def visit_ternary_expr(self, expr: p.TernaryExpr) -> None:
        self.resolve(expr.test)
        self.resolve(expr.if_true)
        self.resolve(expr.if_false)

    def visit_list_expr(self, expr: p.ListExpr) -> None:
        for item in expr.items:
            self.resolve(item)

    def visit_dict_expr(self, expr: p.DictExpr) -> None:
        for key in expr.keys:
            if key is not None:
                self.resolve(key)
        for value in expr.values:
            self.resolve(value)

    def visit_subscript_expr(self, expr: p.SubscriptExpr) -> None:
        self.resolve(expr.object)
        self.resolve(expr.index)

    def visit_slice_expr(self, expr: p.SliceExpr) -> None:
        if expr.lower is not None:
            self.resolve(expr.lower)
        if expr.upper is not None:
            self.resolve(expr.upper)
        if expr.step is not None:
            self.resolve(expr.step)

    def visit_tuple_expr(self, expr: p.TupleExpr) -> None:
        for item in expr.items:
            self.resolve(item)

    def visit_raw_expr(self, expr: p.RawExpr) -> None:
        pass
