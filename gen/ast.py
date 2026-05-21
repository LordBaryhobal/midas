class SimpleTypeStmt:
    name: Token
    template: Optional[TemplateExpr]
    base: SimpleTypeExpr
    constraint: Optional[Expr]

class SimpleTypeExpr:
    name: Token
    optional: bool

class BinaryExpr:
    left: Expr
    operator: Token
    right: Expr

class UnaryExpr:
    operator: Token
    right: Expr

class LiteralExpr:
    value: Any

class WildcardExpr:
    pass

class TemplateExpr:
    type: TypeExpr

class TypeExpr:
    name: Token
    template: Optional[TemplateExpr]
    optional: bool

class ComplexTypeStmt:
    name: Token
    template: Optional[TemplateExpr]
    properties: list[PropertyStmt]

class PropertyStmt:
    name: Token
    type: TypeExpr

class ExtendStmt:
    type: TypeExpr
    operations: list[OpStmt]

class OpStmt:
    name: Token
    operand: TypeExpr
    result: TypeExpr

class PredicateStmt:
    name: Token
    subject: Token
    type: TypeExpr
    condition: Expr
