from typing import Optional

from core.ast.midas import (
    BinaryExpr,
    ComplexTypeStmt,
    Expr,
    ExtendStmt,
    GetExpr,
    GroupingExpr,
    LiteralExpr,
    LogicalExpr,
    OpStmt,
    PredicateStmt,
    PropertyStmt,
    SimpleTypeExpr,
    SimpleTypeStmt,
    Stmt,
    TemplateExpr,
    TypeExpr,
    UnaryExpr,
    VariableExpr,
    WildcardExpr,
)
from lexer.token import Token, TokenType
from parser.base import Parser
from parser.errors import ParsingError


class MidasParser(Parser):
    """A simple parser for midas type definitions"""

    SYNC_BOUNDARY: set[TokenType] = {
        TokenType.TYPE,
        TokenType.OP,
        TokenType.EXTEND,
        TokenType.PREDICATE,
    }

    def parse(self) -> list[Stmt]:
        statements: list[Stmt] = []
        while not self.is_at_end():
            stmt: Optional[Stmt] = self.declaration()
            if stmt is None:
                print("Early stop")
                break
            statements.append(stmt)
        return statements

    def synchronize(self):
        """Skip tokens until a synchronization boundary is found

        This method allows gracefully recovering from a parse error
        to a safe place and continue parsing
        """
        self.advance()
        while not self.is_at_end():
            if self.previous().type == TokenType.NEWLINE:
                return
            if self.peek().type in self.SYNC_BOUNDARY:
                return
            self.advance()

    def declaration(self) -> Optional[Stmt]:
        """Try and parse a declaration

        Any parsing error is caught and None is returned

        Returns:
            Optional[Stmt]: the parsed Midas statement, or None if a ParsingError was raised
        """
        try:
            if self.match(TokenType.TYPE):
                return self.type_declaration()
            if self.match(TokenType.EXTEND):
                return self.extend_declaration()
            if self.match(TokenType.PREDICATE):
                return self.predicate_declaration()
            raise self.error(self.peek(), "Unexpected token")
        except ParsingError:
            self.synchronize()
            return None

    def type_declaration(self) -> SimpleTypeStmt | ComplexTypeStmt:
        """Parse a type declaration

        A type declaration is written `type Name<TypeExpr, ...>` optionally followed by a brace-wrapped body

        Returns:
            TypeStmt: the parsed type declaration statement
        """
        name: Token = self.consume(TokenType.IDENTIFIER, "Expected type name")
        template: Optional[TemplateExpr] = None
        if self.check(TokenType.LEFT_BRACKET):
            template = self.template_expr()

        if self.match(TokenType.LEFT_PAREN):
            base: TypeExpr = self.type_expr()
            self.consume(TokenType.RIGHT_PAREN, "Unclosed base type parenthesis")
            constraint: Optional[Expr] = None
            if self.match(TokenType.WHERE):
                constraint = self.constraint()
            return SimpleTypeStmt(
                name=name, template=template, base=base, constraint=constraint
            )
        else:
            properties: list[PropertyStmt] = self.type_properties()
            return ComplexTypeStmt(name=name, template=template, properties=properties)

    def template_expr(self) -> TemplateExpr:
        self.consume(TokenType.LEFT_BRACKET, "Missing '[' before template expression")
        type: TypeExpr = self.type_expr()
        self.consume(TokenType.RIGHT_BRACKET, "Missing ']' after template expression")
        return TemplateExpr(type=type)

    def type_expr(self) -> TypeExpr:
        """Parse a type expression

        Returns:
            TypeExpr: the parsed type expression
        """
        name: Token = self.consume(TokenType.IDENTIFIER, "Expected type name")
        template: Optional[TemplateExpr] = None
        if self.check(TokenType.LEFT_BRACKET):
            template = self.template_expr()
        optional: bool = self.match(TokenType.QMARK)
        return TypeExpr(name=name, template=template, optional=optional)

    def simple_type_expr(self) -> SimpleTypeExpr:
        name: Token = self.consume(TokenType.IDENTIFIER, "Expected type name")
        optional: bool = self.match(TokenType.QMARK)
        return SimpleTypeExpr(name=name, optional=optional)

    def constraint(self) -> Expr:
        return self.and_()

    def and_(self) -> Expr:
        expr: Expr = self.equality()
        while self.match(TokenType.AND):
            operator: Token = self.previous()
            right: Expr = self.equality()
            expr = LogicalExpr(left=expr, operator=operator, right=right)
        return expr

    def equality(self) -> Expr:
        expr: Expr = self.comparison()
        while self.match(TokenType.BANG_EQUAL, TokenType.EQUAL_EQUAL):
            operator: Token = self.previous()
            right: Expr = self.comparison()
            expr = BinaryExpr(left=expr, operator=operator, right=right)
        return expr

    def comparison(self) -> Expr:
        expr: Expr = self.unary()
        while self.match(
            TokenType.LESS,
            TokenType.LESS_EQUAL,
            TokenType.GREATER,
            TokenType.GREATER_EQUAL,
        ):
            operator: Token = self.previous()
            right: Expr = self.unary()
            expr = BinaryExpr(left=expr, operator=operator, right=right)
        return expr

    def unary(self) -> Expr:
        if self.match(TokenType.MINUS):
            operator: Token = self.previous()
            right: Expr = self.unary()
            return UnaryExpr(operator=operator, right=right)
        return self.reference()

    def reference(self) -> Expr:
        expr: Expr = self.primary()
        while self.match(TokenType.DOT):
            name: Token = self.consume(
                TokenType.IDENTIFIER, "Expected property name after '.'"
            )
            expr = GetExpr(expr=expr, name=name)
        return expr

    def primary(self) -> Expr:
        if self.match(TokenType.FALSE):
            return LiteralExpr(False)
        if self.match(TokenType.TRUE):
            return LiteralExpr(True)
        if self.match(TokenType.NONE):
            return LiteralExpr(None)

        if self.match(TokenType.NUMBER):
            return LiteralExpr(self.previous().value)

        if self.match(TokenType.IDENTIFIER):
            return VariableExpr(self.previous())

        if self.match(TokenType.UNDERSCORE):
            return WildcardExpr(self.previous())

        if self.match(TokenType.LEFT_PAREN):
            expr: Expr = self.constraint()
            self.consume(TokenType.RIGHT_PAREN, "Unclosed parenthesis")
            return GroupingExpr(expr)

        raise self.error(self.peek(), "Expected expression")

    def type_properties(self) -> list[PropertyStmt]:
        """Parse a type definition body

        A type definition body is a set of whitespace-separated
        property statements enclosed in curly braces

        Returns:
            TypeBodyStmt: the parsed type body expression
        """
        self.consume(TokenType.LEFT_BRACE, "Expected '{' to start type body")
        properties: list[PropertyStmt] = []
        while not self.check(TokenType.RIGHT_BRACE) and not self.is_at_end():
            properties.append(self.property_stmt())
        self.consume(TokenType.RIGHT_BRACE, "Unclosed type body")
        return properties

    def property_stmt(self) -> PropertyStmt:
        """Parse a property statement

        A type property statement is written `name: Type`

        Returns:
            PropertyStmt: the parsed property statement
        """
        name: Token = self.consume(TokenType.IDENTIFIER, "Expected property name")
        self.consume(TokenType.COLON, "Expected ':' after property name")
        type: TypeExpr = self.type_expr()
        constraint: Optional[Expr] = None
        if self.match(TokenType.WHERE):
            constraint = self.constraint()
        return PropertyStmt(name=name, type=type, constraint=constraint)

    def extend_declaration(self) -> ExtendStmt:
        type: TypeExpr = self.type_expr()
        self.consume(TokenType.LEFT_BRACE, "Expected '{' to start extend body")
        operations: list[OpStmt] = []
        while not self.is_at_end() and not self.check(TokenType.RIGHT_BRACE):
            operations.append(self.op_declaration())
        self.consume(TokenType.RIGHT_BRACE, "Unclosed extend body")
        return ExtendStmt(type=type, operations=operations)

    def op_declaration(self) -> OpStmt:
        """Parse an operation definition

        An operation is written `op <Type1> operator <Type2> = <Type3>` where `operator` can be any single token

        Returns:
            OpStmt: the parsed operation statement
        """
        self.consume(TokenType.OP, "Expected 'op' keyword")

        name: Token = self.consume(TokenType.IDENTIFIER, "Expected operation name")
        self.consume(TokenType.LEFT_PAREN, "Expected '(' before operand type")
        operand: TypeExpr = self.type_expr()
        self.consume(TokenType.RIGHT_PAREN, "Expected ')' after operand type")

        self.consume(TokenType.ARROW, "Expected '->' before result type")
        result: TypeExpr = self.type_expr()

        return OpStmt(name=name, operand=operand, result=result)

    def predicate_declaration(self) -> PredicateStmt:
        """Parse a type constraint declaration

        A constraint is written `constraint Name = constraint_expression`

        Returns:
            ConstraintStmt: the parsed constraint declaration statement
        """
        name: Token = self.consume(TokenType.IDENTIFIER, "Expected predicate name")
        self.consume(TokenType.LEFT_PAREN, "Expected '(' before predicate subject")
        subject: Token = self.consume(TokenType.IDENTIFIER, "Expected subject name")
        self.consume(TokenType.COLON, "Expected ':' after subject name")
        type: TypeExpr = self.type_expr()
        self.consume(TokenType.RIGHT_PAREN, "Expected ')' after predicate subject")
        self.consume(TokenType.EQUAL, "Expected '=' after predicate subject")
        condition: Expr = self.constraint()
        return PredicateStmt(name=name, subject=subject, type=type, condition=condition)
