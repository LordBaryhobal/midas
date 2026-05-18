from typing import Optional

from core.ast.midas import (
    ConstraintExpr,
    ConstraintStmt,
    OpStmt,
    PropertyStmt,
    Stmt,
    TypeBodyExpr,
    TypeExpr,
    TypeStmt,
)
from lexer.token import Token, TokenType
from parser.base import Parser
from parser.errors import ParsingError


class MidasParser(Parser):
    """A simple parser for midas type definitions"""

    SYNC_BOUNDARY: set[TokenType] = {TokenType.TYPE, TokenType.OP, TokenType.CONSTRAINT}

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
            if self.match(TokenType.OP):
                return self.op_declaration()
            if self.match(TokenType.CONSTRAINT):
                return self.constraint_declaration()
        except ParsingError:
            self.synchronize()
            return None

    def type_declaration(self) -> TypeStmt:
        """Parse a type declaration

        A type declaration is written `type Name<TypeExpr, ...>` optionally followed by a brace-wrapped body

        Returns:
            TypeStmt: the parsed type declaration statement
        """
        name: Token = self.consume(TokenType.IDENTIFIER, "Expected type name")
        self.consume(TokenType.LESS, "Expected '<' after type name")
        bases: list[TypeExpr] = []
        while not self.check(TokenType.GREATER) and not self.is_at_end():
            bases.append(self.type_expr())
            if not self.check(TokenType.GREATER):
                self.consume(TokenType.COMMA, "Expected ',' between type bases")
        self.consume(TokenType.GREATER, "Expected '>' after base type")

        body: Optional[TypeBodyExpr] = None

        if self.check(TokenType.LEFT_BRACE):
            body = self.type_body_expr()
        return TypeStmt(name=name, bases=bases, body=body)

    def type_expr(self) -> TypeExpr:
        """Parse a type expression

        Returns:
            TypeExpr: the parsed type expression
        """
        name: Token = self.consume(TokenType.IDENTIFIER, "Expected type name")
        constraints: list[ConstraintExpr] = []

        while not self.is_at_end() and self.match(TokenType.PLUS):
            constraints.append(self.constraint_expr())

        return TypeExpr(name=name, constraints=constraints)

    def constraint_expr(self) -> ConstraintExpr:
        """Parse a type constraint

        Returns:
            ConstraintExpr: the parsed type constraint expression
        """
        # TODO
        return ConstraintExpr()

    def type_body_expr(self) -> TypeBodyExpr:
        """Parse a type definition body

        A type definition body is a set of whitespace-separated
        property statements enclosed in curly braces

        Returns:
            TypeBodyExpr: the parsed type body expression
        """
        self.consume(TokenType.LEFT_BRACE, "Expected '{' to start type body")
        properties: list[PropertyStmt] = []
        while not self.check(TokenType.RIGHT_BRACE) and not self.is_at_end():
            properties.append(self.property_stmt())
        self.consume(TokenType.RIGHT_BRACE, "Unclosed type body")
        return TypeBodyExpr(properties=properties)

    def property_stmt(self) -> PropertyStmt:
        """Parse a property statement

        A type property statement is written `name: Type`

        Returns:
            PropertyStmt: the parsed property statement
        """
        name: Token = self.consume(TokenType.IDENTIFIER, "Expected property name")
        self.consume(TokenType.COLON, "Expected ':' after property name")
        type: TypeExpr = self.type_expr()
        return PropertyStmt(name=name, type=type)

    def op_declaration(self) -> OpStmt:
        """Parse an operation definition

        An operation is written `op <Type1> operator <Type2> = <Type3>` where `operator` can be any single token

        Returns:
            OpStmt: the parsed operation statement
        """
        self.consume(TokenType.LESS, "Expected '<' before first type")
        left: TypeExpr = self.type_expr()
        self.consume(TokenType.GREATER, "Expected '>' after first type")

        op: Token = self.advance()

        self.consume(TokenType.LESS, "Expected '<' before second type")
        right: TypeExpr = self.type_expr()
        self.consume(TokenType.GREATER, "Expected '>' after second type")

        self.consume(TokenType.EQUAL, "Expected '=' after second type")

        self.consume(TokenType.LESS, "Expected '<' before result type")
        result: TypeExpr = self.type_expr()
        self.consume(TokenType.GREATER, "Expected '>' after result type")

        return OpStmt(left=left, op=op, right=right, result=result)

    def constraint_declaration(self) -> ConstraintStmt:
        """Parse a type constraint declaration

        A constraint is written `constraint Name = constraint_expression`

        Returns:
            ConstraintStmt: the parsed constraint declaration statement
        """
        name: Token = self.consume(TokenType.IDENTIFIER, "Expected constraint name")
        self.consume(TokenType.EQUAL, "Expected '=' after constraint name")
        constraint: ConstraintExpr = self.constraint_expr()
        return ConstraintStmt(name=name, constraint=constraint)
