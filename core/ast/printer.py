from typing import Optional

from core.ast.annotations import Expr, TypeExpr, SchemaExpr, SchemaElementExpr


class AnnotationAstPrinter(Expr.Visitor[str]):
    LAST_CHILD = "└── "
    CHILD = "├── "
    VERTICAL = "│   "
    EMPTY = "    "

    def __init__(self):
        self.level: int = 0
        self.idx: Optional[int] = None
        self.last: bool = False
        self.levels: list[int] = []

    def print(self, expr: Expr):
        return expr.accept(self)

    def print_line(self, text: str) -> str:
        indent: str = ""
        for enabled in self.levels[:-1]:
            if enabled:
                indent += self.VERTICAL
            else:
                indent += self.EMPTY

        if len(self.levels) > 0:
            if self.levels[-1] == 2:
                indent += self.LAST_CHILD
                self.levels[-1] = 0
            else:
                indent += self.CHILD
        if self.idx is not None:
            text = f"[{self.idx}] {text}"
        self.idx = None
        return indent + text + "\n"

    def visit_type_expr(self, expr: TypeExpr) -> str:
        res: str = self.print_line("TypeExpr")
        self.levels.append(1)
        res += self.print_line(f'name: "{expr.name.lexeme}"')
        self.levels[-1] = 2
        if expr.schema is None:
            res += self.print_line("schema: None")
        else:
            res += self.print_line("schema")
            self.levels.append(2)
            res += expr.schema.accept(self)
            self.levels.pop()
        self.levels.pop()
        return res

    def visit_schema_expr(self, expr: SchemaExpr) -> str:
        res: str = self.print_line("SchemaExpr")
        self.levels.append(1)
        for i, elmt in enumerate(expr.elements):
            self.idx = i
            if i == len(expr.elements) - 1:
                self.levels[-1] = 2
            res += elmt.accept(self)
        self.levels.pop()
        return res

    def visit_schema_element_expr(self, expr: SchemaElementExpr) -> str:
        res: str = self.print_line("SchemaElementExpr")
        self.levels.append(1)
        res += self.print_line(
            "name: " + ("None" if expr.name is None else f'"{expr.name.lexeme}"')
        )
        self.levels[-1] = 2
        if expr.type is None:
            res += self.print_line("type: None")
        else:
            res += self.print_line("type")
            self.levels.append(2)
            res += expr.type.accept(self)
            self.levels.pop()
        self.levels.pop()
        return res


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
