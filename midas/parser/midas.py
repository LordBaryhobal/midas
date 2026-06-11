from typing import Optional

from midas.ast.location import Location
from midas.ast.midas import (
    BinaryExpr,
    ComplexType,
    ConstraintType,
    Expr,
    ExtendStmt,
    ExtensionType,
    FunctionType,
    GenericType,
    GetExpr,
    GroupingExpr,
    LiteralExpr,
    LogicalExpr,
    MemberStmt,
    NamedType,
    OpStmt,
    PredicateStmt,
    Stmt,
    Type,
    TypeParam,
    TypeStmt,
    UnaryExpr,
    VariableExpr,
    WildcardExpr,
)
from midas.lexer.token import KEYWORDS, Token, TokenType
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

    def type_declaration(self) -> TypeStmt:
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
        name: Token = self.consume_identifier("Expected type name")
        params: list[TypeParam] = self.type_params()

        self.consume(TokenType.EQUAL, "Expected '=' before type definition")

        type: Type = self.type_expr()

        return TypeStmt(
            location=keyword.location_to(self.previous()),
            name=name,
            params=params,
            type=type,
        )

    def type_params(self) -> list[TypeParam]:
        """Parse a list of type parameters

        Type parameters are a comma-separated list of type variables wrapped in brackets.
        Each type variable is either a simple variable, or a bounded variable written `S <: T`

        Returns:
            list[TypeParam]: the list of type parameters, if any, or an empty list
        """
        if not self.match(TokenType.LEFT_BRACKET):
            return []

        params: list[TypeParam] = []
        while not self.is_at_end() and not self.check(TokenType.RIGHT_BRACKET):
            name: Token = self.consume_identifier("Expected type variable")
            bound: Optional[Type] = None
            if self.match(TokenType.LESS):
                self.consume(TokenType.COLON, "Expected ':' after '<'")
                bound = self.type_expr()
            params.append(
                TypeParam(
                    location=name.location_to(self.previous()),
                    name=name,
                    bound=bound,
                )
            )
            if not self.match(TokenType.COMMA):
                break
        self.consume(TokenType.RIGHT_BRACKET, "Missing ']' after type parameters")
        return params

    def type_expr(self) -> Type:
        """Parse a type expression

        A type is an identifier, optionally followed by a template expression.
        It can also optionally be followed by a '?' to indicate a nullable type

        Returns:
            TypeExpr: the parsed type expression
        """
        base: Type
        if self.match(TokenType.FUNC):
            base = self.function()
        else:
            base = self.constraint_type()
        if self.match(TokenType.AND):
            extension: ComplexType = self.complex_type()
            return ExtensionType(
                location=Location.span(base.location, extension.location),
                base=base,
                extension=extension,
            )
        return base

    def constraint_type(self) -> Type:
        type: Type = self.base_type()
        if self.match(TokenType.WHERE):
            constraint: Expr = self.constraint()
            return ConstraintType(
                location=Location.span(type.location, constraint.location),
                type=type,
                constraint=constraint,
            )
        return type

    def base_type(self) -> Type:
        if self.match(TokenType.LEFT_PAREN):
            type: Type = self.type_expr()
            self.consume(TokenType.RIGHT_PAREN, "Unclosed parenthesis")
            return type

        if self.check(TokenType.LEFT_BRACE):
            return self.complex_type()

        return self.generic_type()

    def generic_type(self) -> Type:
        type: Type = self.named_type()
        if self.check(TokenType.LEFT_BRACKET):
            args: list[Type] = self.type_args()
            return GenericType(
                location=Location.span(type.location, self.previous().get_location()),
                type=type,
                args=args,
            )
        return type

    def type_args(self) -> list[Type]:
        args: list[Type] = []
        self.consume(TokenType.LEFT_BRACKET, "Missing '[' before generic arguments")
        while not self.is_at_end() and not self.check(TokenType.RIGHT_BRACKET):
            args.append(self.type_expr())
            if not self.match(TokenType.COMMA):
                break
        self.consume(TokenType.RIGHT_BRACKET, "Missing ']' after generic arguments")
        return args

    def named_type(self) -> Type:
        name: Token = self.consume_identifier("Expected type name")
        return NamedType(
            location=name.get_location(),
            name=name,
        )

    def complex_type(self) -> ComplexType:
        """Parse a type definition body

        A type definition body is a set of whitespace-separated
        property statements enclosed in curly braces

        Returns:
            ComplexType: the parsed complex type
        """
        left: Token = self.consume(
            TokenType.LEFT_BRACE, "Expected '{' to start type body"
        )
        members: list[MemberStmt] = []
        # TODO: add keyword to differentiate properties and methods,
        # and allow multiple methods with the same name but not properties
        names: set[str] = set()
        while not self.check(TokenType.RIGHT_BRACE) and not self.is_at_end():
            member: MemberStmt = self.member_stmt()
            # if member.name.lexeme in names:
            #    raise self.error(member.name, "Duplicate property")
            # names.add(member.name.lexeme)
            members.append(member)
        right: Token = self.consume(TokenType.RIGHT_BRACE, "Unclosed type body")
        return ComplexType(
            location=left.location_to(right),
            members=members,
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
            location: Location = Location.span(expr.location, right.location)
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
            location: Location = Location.span(expr.location, right.location)
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
            location: Location = Location.span(expr.location, right.location)
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
            location: Location = Location.span(operator.get_location(), right.location)
            return UnaryExpr(location=location, operator=operator, right=right)
        return self.reference()

    def reference(self) -> Expr:
        """Parse an attribute access expression or a simpler expression

        Returns:
            Expr: the parsed expression
        """
        expr: Expr = self.primary()
        while self.match(TokenType.DOT):
            name: Token = self.consume_identifier("Expected property name after '.'")
            location: Location = Location.span(expr.location, name.get_location())
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

        if self.match_identifier():
            return VariableExpr(location=token.get_location(), name=token)

        if self.match(TokenType.UNDERSCORE):
            return WildcardExpr(location=token.get_location(), token=token)

        if self.match(TokenType.LEFT_PAREN):
            expr: Expr = self.constraint()
            right: Token = self.consume(TokenType.RIGHT_PAREN, "Unclosed parenthesis")
            return GroupingExpr(location=token.location_to(right), expr=expr)

        raise self.error(self.peek(), "Expected expression")

    def consume_identifier(self, message: str = "Expected identifier") -> Token:
        if not self.match_identifier():
            raise self.error(self.peek(), message)
        return self.previous()

    def match_identifier(self) -> bool:
        return self.match(TokenType.IDENTIFIER, *KEYWORDS.values())

    def check_identifier(self) -> bool:
        for tt in [TokenType.IDENTIFIER, *KEYWORDS.values()]:
            if self.check(tt):
                return True
        return False

    def member_stmt(self) -> MemberStmt:
        """Parse a member statement

        A type member statement is written `name: Type`

        Returns:
            MemberStmt: the parsed member statement
        """
        name: Token = self.consume_identifier("Expected member name")
        self.consume(TokenType.COLON, "Expected ':' after member name")
        type: Type = self.type_expr()
        return MemberStmt(
            location=name.location_to(self.previous()),
            name=name,
            type=type,
        )

    def extend_declaration(self) -> ExtendStmt:
        """Parse an extension definition

        An extension is written `extend Type { operations }` or `extend[S <: T, U] Type { operations }`

        Returns:
            ExtendStmt: the parsed extension statement
        """
        keyword: Token = self.previous()
        params: list[TypeParam] = self.type_params()

        type: Type = self.type_expr()
        self.consume(TokenType.LEFT_BRACE, "Expected '{' to start extend body")
        operations: list[OpStmt] = []
        while not self.is_at_end() and not self.check(TokenType.RIGHT_BRACE):
            operations.append(self.op_declaration())
        self.consume(TokenType.RIGHT_BRACE, "Unclosed extend body")
        location: Location = keyword.location_to(self.previous())
        return ExtendStmt(
            location=location,
            params=params,
            type=type,
            operations=operations,
        )

    def op_declaration(self) -> OpStmt:
        """Parse an operation definition

        An operation is written `op name(Type) -> Type`

        Returns:
            OpStmt: the parsed operation statement
        """
        keyword: Token = self.consume(TokenType.OP, "Expected 'op' keyword")

        name: Token = self.consume(TokenType.IDENTIFIER, "Expected operation name")
        self.consume(TokenType.LEFT_PAREN, "Expected '(' before operand type")
        operand: Type = self.type_expr()
        self.consume(TokenType.RIGHT_PAREN, "Expected ')' after operand type")

        self.consume(TokenType.ARROW, "Expected '->' before result type")
        result: Type = self.type_expr()

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
        name: Token = self.consume_identifier("Expected predicate name")
        self.consume(TokenType.LEFT_PAREN, "Expected '(' before predicate subject")
        subject: Token = self.consume_identifier("Expected subject name")
        self.consume(TokenType.COLON, "Expected ':' after subject name")
        type: Type = self.type_expr()
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

    def function(self) -> FunctionType:
        l_paren: Token = self.consume(
            TokenType.LEFT_PAREN, "Expected '(' before function parameters"
        )
        pos_args: list[FunctionType.Argument] = []
        kw_args: list[FunctionType.Argument] = []

        positional: bool = True
        while not self.is_at_end() and not self.check(TokenType.RIGHT_PAREN):
            if positional and (
                self.match(TokenType.STAR) or self.match(TokenType.SLASH)
            ):
                positional = False
            else:
                name: Optional[Token] = None
                if self.check_identifier() and self.check_next(TokenType.COLON):
                    name = self.advance()
                    self.advance()
                type: Type = self.type_expr()
                optional: bool = self.match(TokenType.QMARK)
                arg = FunctionType.Argument(
                    location=None,
                    name=name,
                    type=type,
                    required=not optional,
                )
                if positional:
                    pos_args.append(arg)
                else:
                    kw_args.append(arg)

            if not self.match(TokenType.COMMA):
                break
        self.consume(TokenType.RIGHT_PAREN, "Expected ')' after function parameters")

        self.consume(TokenType.ARROW, "Expected '->' before result type")
        result: Type = self.type_expr()

        return FunctionType(
            location=l_paren.location_to(self.previous()),
            pos_args=pos_args,
            kw_args=kw_args,
            returns=result,
        )
