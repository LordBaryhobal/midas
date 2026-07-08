import midas.ast.midas as m


class MidasPrinter(
    m.Expr.Visitor[str],
    m.Stmt.Visitor[str],
    m.Type.Visitor[str],
):
    def __init__(self, indent: int = 4):
        self.indent: int = indent
        self.level: int = 0

    def indented(self, text: str) -> str:
        return " " * (self.level * self.indent) + text

    def print(self, expr: m.Expr | m.Stmt | m.Type) -> str:
        self.level = 0
        return expr.accept(self)

    # Statements

    def visit_type_stmt(self, stmt: m.TypeStmt) -> str:
        template: str = ""
        if len(stmt.params) != 0:
            params: list[str] = [self._print_type_param(param) for param in stmt.params]
            template = f"[{', '.join(params)}]"
        res: str = f"type {stmt.name.lexeme}{template} = {stmt.type.accept(self)}"
        return self.indented(res)

    def visit_alias_stmt(self, stmt: m.AliasStmt) -> str:
        return self.indented(f"alias {stmt.name.lexeme} = {stmt.type.accept(self)}")

    def _print_type_param(self, param: m.TypeParam) -> str:
        res: str = param.name.lexeme
        if param.bound is not None:
            res += "<:" + param.bound.accept(self)
        return res

    def visit_member_stmt(self, stmt: m.MemberStmt):
        keyword: str = {
            m.MemberKind.PROPERTY: "prop",
            m.MemberKind.METHOD: "def",
        }.get(stmt.kind, "")
        res: str = f"{keyword} {stmt.name.lexeme}: {stmt.type.accept(self)}"
        return self.indented(res)

    def visit_extend_stmt(self, stmt: m.ExtendStmt):
        template: str = ""
        if len(stmt.params) != 0:
            params: list[str] = [self._print_type_param(param) for param in stmt.params]
            template = f"[{', '.join(params)}]"
        res: str = self.indented(f"extend {stmt.name.lexeme}{template}")
        res += " {\n"
        self.level += 1
        for member in stmt.members:
            res += member.accept(self) + "\n"
        self.level -= 1
        res += self.indented("}")
        return res

    def visit_predicate_stmt(self, stmt: m.PredicateStmt):
        name: str = stmt.name.lexeme
        sig: str = "".join(self._visit_param_spec(spec) for spec in stmt.params)
        body: str = stmt.body.accept(self)
        return self.indented(f"predicate {name}{sig} = {body}")

    # Expressions

    def visit_logical_expr(self, expr: m.LogicalExpr):
        left: str = expr.left.accept(self)
        operator: str = expr.operator.lexeme
        right: str = expr.right.accept(self)
        return f"{left} {operator} {right}"

    def visit_binary_expr(self, expr: m.BinaryExpr):
        left: str = expr.left.accept(self)
        operator: str = expr.operator.lexeme
        right: str = expr.right.accept(self)
        return f"{left} {operator} {right}"

    def visit_unary_expr(self, expr: m.UnaryExpr):
        operator: str = expr.operator.lexeme
        right: str = expr.right.accept(self)
        return f"{operator}{right}"

    def visit_call_expr(self, expr: m.CallExpr) -> str:
        args: list[str] = [arg.accept(self) for arg in expr.arguments] + [
            f"{name}={arg.accept(self)}" for name, arg in expr.keywords.items()
        ]
        return f"{expr.callee.accept(self)}({', '.join(args)})"

    def visit_get_expr(self, expr: m.GetExpr):
        expr_: str = expr.expr.accept(self)
        name: str = expr.name.lexeme
        return f"{expr_}.{name}"

    def visit_variable_expr(self, expr: m.VariableExpr):
        return expr.name.lexeme

    def visit_grouping_expr(self, expr: m.GroupingExpr):
        expr_: str = expr.expr.accept(self)
        return f"({expr_})"

    def visit_literal_expr(self, expr: m.LiteralExpr):
        return str(expr.value)

    def visit_wildcard_expr(self, expr: m.WildcardExpr):
        return "_"

    # Types

    def visit_named_type(self, type: m.NamedType) -> str:
        return type.name.lexeme

    def visit_generic_type(self, type: m.GenericType) -> str:
        res: str = type.type.accept(self)
        if len(type.args) != 0:
            args: list[str] = [param.accept(self) for param in type.args]
            res += f"[{', '.join(args)}]"
        return res

    def visit_constraint_type(self, type: m.ConstraintType) -> str:
        res: str = type.type.accept(self)
        res += " where " + type.constraint.accept(self)
        return res

    def visit_function_type(self, type: m.FunctionType) -> str:
        spec: str = self._visit_param_spec(type.params)
        return f"fn {spec} -> {type.returns.accept(self)}"

    def _visit_param_spec(self, spec: m.ParamSpec) -> str:
        pos: list[str] = [self._print_param(param) for param in spec.pos]
        mixed: list[str] = [self._print_param(param) for param in spec.mixed]
        kw: list[str] = [self._print_param(param) for param in spec.kw]
        params: list[str] = pos

        if len(pos) != 0:
            params.append("/")
        params += mixed
        if len(kw) != 0:
            params.append("*")
        params += kw
        return f"({', '.join(params)})"

    def _print_param(self, param: m.FunctionType.Parameter) -> str:
        res: str = ""
        if param.name is not None:
            res += param.name.lexeme
            res += ": "
        res += param.type.accept(self)
        if not param.required:
            res += "?"
        return res

    def visit_frame_type(self, type: m.FrameType) -> str:
        res: str = self.indented("Frame[")
        if len(type.columns) != 0:
            res += "\n"
            self.level += 1
            columns: list[str] = []
            for column in type.columns:
                columns.append(self.indented(self._print_frame_column(column)))
            res += ",\n".join(columns)
            self.level -= 1
            res += "\n"
        res += "]"
        return res

    def _print_frame_column(self, column: m.FrameType.Column) -> str:
        return f"{column.name.lexeme}: {column.type.accept(self)}"
