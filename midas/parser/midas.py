from typing import Optional

from midas.ast.location import Location
from midas.ast.midas import (
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
from midas.lexer.token import Token, TokenType
from midas.parser.base import Parser
from midas.parser.errors import ParsingError


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

        A type declaration can either be a simple type alias or a new complex type.
        In either case, it can have an optional template expression after its name, wrapped in brackets.
        A simple type alias is derived from a base type expression, and can have a optional constraint expression preceded by the `where` keyword.
        A full simple type alias is thus written:
        ```
        type Name[Template](TypeExpr) where Condition
        ```

        A new complex type has a set of properties which are named, have a type and an optional constraint expression (also preceded by the `where` keyword).
        A full complex type definition is thus written:
        ```
        type Name[Template] {
            prop1: TypeExpr1 where Condition1
            prop2: TypeExpr2 where Condition2
            ...
        }
        ```

        Returns:
            TypeStmt: the parsed type declaration statement
        """
        keyword: Token = self.previous()
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
                location=keyword.location_to(self.previous()),
                name=name,
                template=template,
                base=base,
                constraint=constraint,
            )
        else:
            properties: list[PropertyStmt] = self.type_properties()
            return ComplexTypeStmt(
                location=keyword.location_to(self.previous()),
                name=name,
                template=template,
                properties=properties,
            )

    def template_expr(self) -> TemplateExpr:
        """Parse a generic template expression

        A template is written `[TypeExpr]`

        Returns:
            TemplateExpr: the parsed template expression
        """
        left: Token = self.consume(
            TokenType.LEFT_BRACKET, "Missing '[' before template expression"
        )
        type: TypeExpr = self.type_expr()
        right: Token = self.consume(
            TokenType.RIGHT_BRACKET, "Missing ']' after template expression"
        )
        return TemplateExpr(location=left.location_to(right), type=type)

    def type_expr(self) -> TypeExpr:
        """Parse a type expression

        A type is an identifier, optionally followed by a template expression.
        It can also optionally be followed by a '?' to indicate a nullable type

        Returns:
            TypeExpr: the parsed type expression
        """
        name: Token = self.consume(TokenType.IDENTIFIER, "Expected type name")
        template: Optional[TemplateExpr] = None
        if self.check(TokenType.LEFT_BRACKET):
            template = self.template_expr()
        optional: bool = self.match(TokenType.QMARK)
        return TypeExpr(
            location=name.location_to(self.previous()),
            name=name,
            template=template,
            optional=optional,
        )

    def simple_type_expr(self) -> SimpleTypeExpr:
        """Parse a simple type expression

        A simple type is just an identifier optionally followed by a '?'

        Returns:
            SimpleTypeExpr: the parsed simple type expression
        """
        name: Token = self.consume(TokenType.IDENTIFIER, "Expected type name")
        optional: bool = self.match(TokenType.QMARK)
        return SimpleTypeExpr(
            location=name.location_to(self.previous()), name=name, optional=optional
        )

    def constraint(self) -> Expr:
        """Parse a constraint

        A constraint is basically a logical predicate

        Returns:
            Expr: the parsed constraint expression
        """
        return self.and_()

    def and_(self) -> Expr:
        """Parse a logical AND expression or a simpler expression

        Returns:
            Expr: the parsed expression
        """
        expr: Expr = self.equality()
        while self.match(TokenType.AND):
            operator: Token = self.previous()
            right: Expr = self.equality()
            location: Optional[Location] = None
            if expr.location and right.location:
                location = Location.span(expr.location, right.location)
            expr = LogicalExpr(
                location=location, left=expr, operator=operator, right=right
            )
        return expr

    def equality(self) -> Expr:
        """Parse a logical equality expression or a simpler expression

        Returns:
            Expr: the parsed expression
        """
        expr: Expr = self.comparison()
        while self.match(TokenType.BANG_EQUAL, TokenType.EQUAL_EQUAL):
            operator: Token = self.previous()
            right: Expr = self.comparison()
            location: Optional[Location] = None
            if expr.location and right.location:
                location = Location.span(expr.location, right.location)
            expr = BinaryExpr(
                location=location, left=expr, operator=operator, right=right
            )
        return expr

    def comparison(self) -> Expr:
        """Parse a logical comparison expression or a simpler expression

        Returns:
            Expr: the parsed expression
        """
        expr: Expr = self.unary()
        while self.match(
            TokenType.LESS,
            TokenType.LESS_EQUAL,
            TokenType.GREATER,
            TokenType.GREATER_EQUAL,
        ):
            operator: Token = self.previous()
            right: Expr = self.unary()
            location: Optional[Location] = None
            if expr.location and right.location:
                location = Location.span(expr.location, right.location)
            expr = BinaryExpr(
                location=location, left=expr, operator=operator, right=right
            )
        return expr

    def unary(self) -> Expr:
        """Parse a unary expression or a simpler expression

        Returns:
            Expr: the parsed expression
        """
        if self.match(TokenType.MINUS):
            operator: Token = self.previous()
            right: Expr = self.unary()
            location: Optional[Location] = None
            if right.location:
                location = Location.span(operator.get_location(), right.location)
            return UnaryExpr(location=location, operator=operator, right=right)
        return self.reference()

    def reference(self) -> Expr:
        """Parse an attribute access expression or a simpler expression

        Returns:
            Expr: the parsed expression
        """
        expr: Expr = self.primary()
        while self.match(TokenType.DOT):
            name: Token = self.consume(
                TokenType.IDENTIFIER, "Expected property name after '.'"
            )
            location: Optional[Location] = None
            if expr.location:
                location = Location.span(expr.location, name.get_location())
            expr = GetExpr(location=location, expr=expr, name=name)
        return expr

    def primary(self) -> Expr:
        """Parse a primary expression

        This includes literals (booleans, numbers, etc.), wildcards, identifiers and grouped expressions

        Returns:
            Expr: the parsed expression
        """
        token: Token = self.peek()
        if self.match(TokenType.FALSE):
            return LiteralExpr(location=token.get_location(), value=False)
        if self.match(TokenType.TRUE):
            return LiteralExpr(location=token.get_location(), value=True)
        if self.match(TokenType.NONE):
            return LiteralExpr(location=token.get_location(), value=None)

        if self.match(TokenType.NUMBER):
            return LiteralExpr(location=token.get_location(), value=token.value)

        if self.match(TokenType.IDENTIFIER):
            return VariableExpr(location=token.get_location(), name=token)

        if self.match(TokenType.UNDERSCORE):
            return WildcardExpr(location=token.get_location(), token=token)

        if self.match(TokenType.LEFT_PAREN):
            expr: Expr = self.constraint()
            right: Token = self.consume(TokenType.RIGHT_PAREN, "Unclosed parenthesis")
            return GroupingExpr(location=token.location_to(right), expr=expr)

        raise self.error(self.peek(), "Expected expression")

    def type_properties(self) -> list[PropertyStmt]:
        """Parse a type definition body

        A type definition body is a set of whitespace-separated
        property statements enclosed in curly braces

        Returns:
            list[PropertyStmt]: the parsed type properties
        """
        self.consume(TokenType.LEFT_BRACE, "Expected '{' to start type body")
        properties: list[PropertyStmt] = []
        while not self.check(TokenType.RIGHT_BRACE) and not self.is_at_end():
            properties.append(self.property_stmt())
        self.consume(TokenType.RIGHT_BRACE, "Unclosed type body")
        return properties

    def property_stmt(self) -> PropertyStmt:
        """Parse a property statement

        A type property statement is written `name: Type` or `name: Type where Condition`

        Returns:
            PropertyStmt: the parsed property statement
        """
        name: Token = self.consume(TokenType.IDENTIFIER, "Expected property name")
        self.consume(TokenType.COLON, "Expected ':' after property name")
        type: TypeExpr = self.type_expr()
        constraint: Optional[Expr] = None
        if self.match(TokenType.WHERE):
            constraint = self.constraint()
        return PropertyStmt(
            location=name.location_to(self.previous()),
            name=name,
            type=type,
            constraint=constraint,
        )

    def extend_declaration(self) -> ExtendStmt:
        """Parse an extension definition

        An extension is written `extend Type { operations }`

        Returns:
            ExtendStmt: the parsed extension statement
        """
        keyword: Token = self.previous()
        type: TypeExpr = self.type_expr()
        self.consume(TokenType.LEFT_BRACE, "Expected '{' to start extend body")
        operations: list[OpStmt] = []
        while not self.is_at_end() and not self.check(TokenType.RIGHT_BRACE):
            operations.append(self.op_declaration())
        self.consume(TokenType.RIGHT_BRACE, "Unclosed extend body")
        location: Optional[Location] = None
        if type.location:
            location = keyword.location_to(self.previous())
        return ExtendStmt(location=location, type=type, operations=operations)

    def op_declaration(self) -> OpStmt:
        """Parse an operation definition

        An operation is written `op name(Type) -> Type`

        Returns:
            OpStmt: the parsed operation statement
        """
        keyword: Token = self.consume(TokenType.OP, "Expected 'op' keyword")

        name: Token = self.consume(TokenType.IDENTIFIER, "Expected operation name")
        self.consume(TokenType.LEFT_PAREN, "Expected '(' before operand type")
        operand: TypeExpr = self.type_expr()
        self.consume(TokenType.RIGHT_PAREN, "Expected ')' after operand type")

        self.consume(TokenType.ARROW, "Expected '->' before result type")
        result: TypeExpr = self.type_expr()

        return OpStmt(
            location=keyword.location_to(self.previous()),
            name=name,
            operand=operand,
            result=result,
        )

    def predicate_declaration(self) -> PredicateStmt:
        """Parse a predicate declaration

        A predicate is written `predicate Name(subject: Type) = constraint_expression`

        Returns:
            PredicateStmt: the parsed predicate declaration statement
        """
        keyword: Token = self.previous()
        name: Token = self.consume(TokenType.IDENTIFIER, "Expected predicate name")
        self.consume(TokenType.LEFT_PAREN, "Expected '(' before predicate subject")
        subject: Token = self.consume(TokenType.IDENTIFIER, "Expected subject name")
        self.consume(TokenType.COLON, "Expected ':' after subject name")
        type: TypeExpr = self.type_expr()
        self.consume(TokenType.RIGHT_PAREN, "Expected ')' after predicate subject")
        self.consume(TokenType.EQUAL, "Expected '=' after predicate subject")
        condition: Expr = self.constraint()
        return PredicateStmt(
            location=keyword.location_to(self.previous()),
            name=name,
            subject=subject,
            type=type,
            condition=condition,
        )
