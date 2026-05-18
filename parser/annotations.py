from typing import Optional

from core.ast.annotations import Expr, SchemaElementExpr, SchemaExpr, TypeExpr
from lexer.token import Token, TokenType
from parser.base import Parser
from parser.errors import ParsingError


class AnnotationParser(Parser):
    """A simple parser for custom type annotations"""

    SYNC_BOUNDARY: set[TokenType] = set()

    def parse(self) -> Optional[Expr]:
        expression: Optional[Expr] = self.annotation()
        if not self.is_at_end():
            self.error(self.peek(), "Extra tokens")
        return expression

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

    def annotation(self) -> Optional[Expr]:
        """Try and parse an annotation

        Any parsing error is caught and None is returned

        Returns:
            Optional[Expr]: the parsed annotation expression, or None if a ParsingError was raised
        """
        try:
            return self.type()
        except ParsingError:
            self.synchronize()
            return None

    def type(self) -> TypeExpr:
        """Parse a type definition

        `Type` or `Type[Schema]`

        Returns:
            TypeExpr: the parsed type expression
        """
        name: Token = self.consume(TokenType.IDENTIFIER, "Expected type identifier")
        schema: Optional[SchemaExpr] = None
        if self.match(TokenType.LEFT_BRACKET):
            schema = self.schema()
        return TypeExpr(name=name, schema=schema)

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
            type = self.type()
        return SchemaElementExpr(name=name, type=type)
