from typing import Optional

from core.ast.midas import ConstraintExpr, Stmt, TypeBodyExpr, TypeExpr, TypeStmt
from lexer.token import Token, TokenType
from parser.base import Parser
from parser.errors import ParsingError


class MidasParser(Parser):
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
        self.advance()
        while not self.is_at_end():
            if self.previous().type == TokenType.NEWLINE:
                return
            if self.peek().type in self.SYNC_BOUNDARY:
                return
            self.advance()

    def declaration(self) -> Optional[Stmt]:
        try:
            if self.match(TokenType.TYPE):
                return self.type_declaration()
            # if self.match(TokenType.OP):
            #     return self.op_declaration()
            # if self.match(TokenType.CONSTRAINT):
            #     return self.constraint_declaration()
        except ParsingError:
            self.synchronize()
            return None

    def type_declaration(self) -> TypeStmt:
        name: Token = self.consume(TokenType.IDENTIFIER, "Expected type name")
        self.consume(TokenType.LESS, "Expected '<' after type name")
        bases: list[TypeExpr] = []
        while not self.check(TokenType.GREATER) and not self.is_at_end():
            bases.append(self.type_expr())
            if not self.check(TokenType.GREATER):
                self.consume(TokenType.COMMA, "Expected ',' between type bases")
        self.consume(TokenType.GREATER, "Expected '>' after base type")

        body: Optional[TypeBodyExpr] = None
        return TypeStmt(name=name, bases=bases, body=body)

    def type_expr(self) -> TypeExpr:
        name: Token = self.consume(TokenType.IDENTIFIER, "Expected type name")
        constraints: list[ConstraintExpr] = []

        while not self.is_at_end() and self.match(TokenType.PLUS):
            constraints.append(self.constraint_expr())

        return TypeExpr(name=name, constraints=constraints)

    def constraint_expr(self) -> ConstraintExpr:
        # TODO
        return ConstraintExpr()
