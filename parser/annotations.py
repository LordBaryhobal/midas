from typing import Optional

from core.ast.annotations import (
    AnnotationStmt,
    ConstraintExpr,
    Expr,
    LiteralExpr,
    SchemaElementExpr,
    SchemaExpr,
    Stmt,
    TypeExpr,
    WildcardExpr,
)
from lexer.token import Token, TokenType
from parser.base import Parser
from parser.errors import ParsingError


class AnnotationParser(Parser):
    """A simple parser for custom type annotations"""

    SYNC_BOUNDARY: set[TokenType] = set()

    def parse(self) -> Optional[Stmt]:
        stmt: Optional[Stmt] = None
        try:
            stmt = self.annotation()
        except ParsingError:
            self.synchronize()
        if not self.is_at_end():
            self.error(self.peek(), "Extra tokens")
        return stmt

    def synchronize(self):
        """Skip tokens until a synchronization boundary is found

        This method allows gracefully recovering from a parse error
        to a safe place and continue parsing
        """
        self.advance()
        while not self.is_at_end():
            if self.peek().type in self.SYNC_BOUNDARY:
                return
            self.advance()

    def annotation(self) -> AnnotationStmt:
        """Parse an annotation

        An annotation is written as `Type` or `Type[Schema]`

        Returns:
            AnnotationStmt: the parsed annotation statement
        """

        name: Token = self.consume(TokenType.IDENTIFIER, "Expected type identifier")
        schema: Optional[SchemaExpr] = None
        if self.match(TokenType.LEFT_BRACKET):
            schema = self.schema()
        return AnnotationStmt(name=name, schema=schema)

    def type_expr(self) -> TypeExpr:
        """Parse a type expression

        Returns:
            TypeExpr: the parsed type expression
        """
        name: Token = self.consume(TokenType.IDENTIFIER, "Expected type name")
        constraints: list[ConstraintExpr] = []

        while not self.is_at_end() and self.match(TokenType.PLUS):
            print(self.peek())
            print(self.tokens)
            self.consume(TokenType.LEFT_PAREN, "Expected '(' before type constraint")
            constraints.append(self.constraint_expr())
            self.consume(TokenType.RIGHT_PAREN, "Expected ')' after type constraint")

        return TypeExpr(name=name, constraints=constraints)

    def constraint_expr(self) -> ConstraintExpr:
        """Parse a type constraint

        Returns:
            ConstraintExpr: the parsed type constraint expression
        """
        
        left: Expr = self.constraint_value()
        op: Token = self.constraint_operator()
        right: Expr = self.constraint_value()
        return ConstraintExpr(left=left, op=op, right=right)

    def constraint_value(self) -> Expr:
        if self.match(TokenType.UNDERSCORE):
            return WildcardExpr(self.previous())
        return self.literal()

    def literal(self) -> LiteralExpr:
        if self.match(TokenType.FALSE):
            return LiteralExpr(False)
        if self.match(TokenType.TRUE):
            return LiteralExpr(True)
        if self.match(TokenType.NONE):
            return LiteralExpr(None)
        
        if self.match(TokenType.NUMBER):
            return LiteralExpr(self.previous().value)
        
        raise self.error(self.peek(), "Expected literal")

    def constraint_operator(self) -> Token:
        if self.match(TokenType.LESS, TokenType.LESS_EQUAL, TokenType.GREATER, TokenType.GREATER_EQUAL, TokenType.EQUAL_EQUAL, TokenType.BANG_EQUAL):
            return self.previous()
        raise self.error(self.peek(), "Expected constraint operator")

    def schema(self) -> SchemaExpr:
        """Parse a schema definition

        A comma separated list of schema elements

        Returns:
            SchemaExpr: the parsed schema expression
        """
        left: Token = self.previous()
        elements: list[Expr] = []
        while not self.check(TokenType.RIGHT_BRACKET) and not self.is_at_end():
            elements.append(self.schema_element())
            if not self.check(TokenType.RIGHT_BRACKET):
                self.consume(TokenType.COMMA, "Expected ',' between schema elements")

        right: Token = self.consume(TokenType.RIGHT_BRACKET, "Unclosed schema")
        return SchemaExpr(left=left, elements=elements, right=right)

    def schema_element(self) -> SchemaElementExpr:
        """Parse a schema element

        An anonymous element (`_`), a type, an untyped named column (`name: _`),
        or a named column (`name: Type`)

        Returns:
            SchemaElementExpr: the parsed schema element expression
        """
        if self.match(TokenType.UNDERSCORE):
            return SchemaElementExpr(name=None, type=None)

        if not self.check(TokenType.IDENTIFIER):
            raise self.error(self.peek(), "Expected schema element")

        name: Optional[Token] = None
        type: Optional[TypeExpr] = None
        if self.check_next(TokenType.COLON):
            name = self.advance()
            self.advance()
        if not self.match(TokenType.UNDERSCORE):
            type = self.type_expr()
        return SchemaElementExpr(name=name, type=type)
