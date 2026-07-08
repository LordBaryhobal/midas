from typing import Optional

from midas.ast.location import Location
from midas.ast.midas import (
    AliasStmt,
    BinaryExpr,
    CallExpr,
    ConstraintType,
    Expr,
    ExtendStmt,
    FrameType,
    FunctionType,
    GenericType,
    GetExpr,
    GroupingExpr,
    LiteralExpr,
    LogicalExpr,
    MemberKind,
    MemberStmt,
    NamedType,
    ParamSpec,
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


class MidasParser(Parser[list[Stmt]]):
    """A simple parser for midas type definitions"""

    SYNC_BOUNDARY: set[TokenType] = {
        TokenType.ALIAS,
        TokenType.TYPE,
        TokenType.EXTEND,
        TokenType.PREDICATE,
        TokenType.PROP,
        TokenType.FUNC,
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

        Any parsing error is caught and `None` is returned

        Returns:
            Optional[Stmt]: the parsed Midas statement, or `None` if a ParsingError was raised
        """
        try:
            if self.match(TokenType.TYPE):
                return self.type_declaration()
            if self.match(TokenType.ALIAS):
                return self.alias_declaration()
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

        A type declaration creates a named subtype of a type expression.
        It can have an optional template expression after its name, wrapped in brackets, to handle type parameters.

        A type statement consists of:
        - the `type` keyword
        - a name (identifier)
        - (optional) type parameters
        - a body, a type expression (see :func:`type_expr`)

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

    def alias_declaration(self) -> AliasStmt:
        """Parse an alias declaration

        An alias statement consists of:
        - the `alias` keyword
        - a name (identifier)
        - a body, a type expression (see :func:`type_expr`)

        Returns:
            AliasStmt: the parsed alias declaration statement
        """
        keyword: Token = self.previous()
        name: Token = self.consume_identifier("Expected alias name")

        self.consume(TokenType.EQUAL, "Expected '=' before alias definition")

        type: Type = self.type_expr()

        return AliasStmt(
            location=keyword.location_to(self.previous()),
            name=name,
            type=type,
        )

    def type_expr(self) -> Type:
        """Parse a type expression

        A type expression can either be a function type (see :func:`function`)
        or a constraint type (see :func:`constraint_type`)

        Returns:
            TypeExpr: the parsed type expression
        """
        if self.match(TokenType.FUNC):
            return self.function()
        return self.constraint_type()

    def constraint_type(self) -> Type:
        """Parse a constraint type expression

        A constraint type consists of a base type (see :func:`base_type`),
        optionally followed by the `where` keyword and a constraint
        expression (see :func:`constraint`)

        Returns:
            Type: the parsed constraint type expression
        """
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
        """Parse a base type expression

        A base type is either a parenthesized type expression (see :func:`type_expr`)
        or a generic type (see :func:`generic_type`)

        Returns:
            Type: the parsed base type expression
        """
        if self.match(TokenType.LEFT_PAREN):
            type: Type = self.type_expr()
            self.consume(TokenType.RIGHT_PAREN, "Unclosed parenthesis")
            return type

        return self.generic_type()

    def generic_type(self) -> Type:
        """Parse a generic type expression

        A generic type consists of a named type (see :func:`named_type`),
        optionally followed by type arguments in brackets.

        The special `Frame` type accepts a frame schema instead of type
        arguments (see :func:`frame_type`).

        Returns:
            Type: the parsed generic type
        """
        type: NamedType = self.named_type()
        if self.check(TokenType.LEFT_BRACKET):
            if type.name.lexeme == "Frame":
                return self.frame_type()
            args: list[Type] = self.type_args()
            return GenericType(
                location=Location.span(type.location, self.previous().get_location()),
                type=type,
                args=args,
            )
        return type

    def type_args(self) -> list[Type]:
        """Parse a list of type arguments

        Type arguments are a comma-separated list of type expression wrapped in brackets.

        Returns:
            list[Type]: the list of type arguments, if any, or an empty list
        """
        args: list[Type] = []
        self.consume(TokenType.LEFT_BRACKET, "Missing '[' before generic arguments")
        while not self.is_at_end() and not self.check(TokenType.RIGHT_BRACKET):
            args.append(self.type_expr())
            if not self.match(TokenType.COMMA):
                break
        self.consume(TokenType.RIGHT_BRACKET, "Missing ']' after generic arguments")
        return args

    def named_type(self) -> NamedType:
        """Parse a named type expression

        A named type is an identifier token

        Returns:
            NamedType: the parsed named type expression
        """
        name: Token = self.consume_identifier("Expected type name")
        return NamedType(
            location=name.get_location(),
            name=name,
        )

    def frame_type(self) -> FrameType:
        """Parse a frame type expression

        A frame type consists of:
        - the `Frame` identifier
        - an opening bracket `[`
        - a list of comma-separated column expression consisting of:
            - a name (token)
            - a colon `:`
            - a type expression (see :func:`type_expr`)
        - a closing bracket `]`

        Returns:
            FrameType: the parsed frame type
        """
        keyword: Token = self.previous()
        self.consume(TokenType.LEFT_BRACKET, "Expected '[' to start frame schema")

        columns: list[FrameType.Column] = []
        while not self.check(TokenType.RIGHT_BRACKET) and not self.is_at_end():
            name: Token = self.advance()
            self.consume(TokenType.COLON, "Expected ':' between column name and type")
            type: Type = self.type_expr()
            columns.append(
                FrameType.Column(
                    location=name.location_to(self.previous()),
                    name=name,
                    type=type,
                )
            )
            if not self.match(TokenType.COMMA):
                break

        self.consume(TokenType.RIGHT_BRACKET, "Unclosed frame schema")

        return FrameType(
            location=keyword.location_to(self.previous()),
            columns=columns,
        )

    def constraint(self) -> Expr:
        """Parse a constraint expression

        A constraint is an expression (see :func:`expression`)

        Returns:
            Expr: the parsed constraint expression
        """
        return self.expression()

    def expression(self) -> Expr:
        """Parse an expression

        An expression consists of a logical AND expression (see :func:`and_`)

        Returns:
            Expr: the parsed expression
        """
        return self.and_()

    def and_(self) -> Expr:
        """Parse a logical AND expression

        An AND consists of one or more equality expressions (see :func:`equality`)
        separated by logical AND operators (`&`)

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
        """Parse an equality expression

        An equality consists of one or more comparison expressions (see :func:`comparison`)
        separated by equality operators (`==`, `!=`)

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
        """Parse a comparison expression

        A comparison consists of one or more term expressions (see :func:`term`)
        separated by comparison operators (`<`, `<=`, `>`, `>=`)

        Returns:
            Expr: the parsed expression
        """
        expr: Expr = self.term()
        while self.match(
            TokenType.LESS,
            TokenType.LESS_EQUAL,
            TokenType.GREATER,
            TokenType.GREATER_EQUAL,
        ):
            operator: Token = self.previous()
            right: Expr = self.term()
            location: Location = Location.span(expr.location, right.location)
            expr = BinaryExpr(
                location=location, left=expr, operator=operator, right=right
            )
        return expr

    def term(self) -> Expr:
        """Parse a term expression

        A term consists of one or more factor expressions (see :func:`factor`)
        separated by weak arithmetic operators (`+`, `-`)

        Returns:
            Expr: the parsed expression
        """
        expr: Expr = self.factor()
        while self.match(TokenType.PLUS, TokenType.MINUS):
            operator: Token = self.previous()
            right: Expr = self.factor()
            location: Location = Location.span(expr.location, right.location)
            expr = BinaryExpr(
                location=location, left=expr, operator=operator, right=right
            )
        return expr

    def factor(self) -> Expr:
        """Parse a factor expression

        A factor consists of one or more unary expressions (see :func:`unary`)
        separated by strong arithmetic operators (`*`, `/`)

        Returns:
            Expr: the parsed expression
        """
        expr: Expr = self.unary()
        while self.match(TokenType.STAR, TokenType.SLASH):
            operator: Token = self.previous()
            right: Expr = self.unary()
            location: Location = Location.span(expr.location, right.location)
            expr = BinaryExpr(
                location=location, left=expr, operator=operator, right=right
            )
        return expr

    def unary(self) -> Expr:
        """Parse a unary expression

        A unary consists of a call expression (see :func:`call`) optionally
        preceded by zero or more unary operators (`+`, `-`, `!`)

        Returns:
            Expr: the parsed expression
        """
        if self.match(TokenType.PLUS, TokenType.MINUS, TokenType.BANG):
            operator: Token = self.previous()
            right: Expr = self.unary()
            location: Location = Location.span(operator.get_location(), right.location)
            return UnaryExpr(location=location, operator=operator, right=right)
        return self.call()

    def call(self) -> Expr:
        """Parse a call expression

        A call consists of a reference expression (see :func:`reference`)
        optionally followed by zero or more argument groups.

        Argument groups are parenthesize, comma-separated list of arguments (see :func:`finish_call`)

        Returns:
            Expr: the parsed expression
        """
        expr: Expr = self.reference()
        while self.match(TokenType.LEFT_PAREN):
            expr = self.finish_call(expr)
        return expr

    def finish_call(self, callee: Expr) -> Expr:
        """Parse an argument group, i.e. the arguments of a call

        Arguments are either passed positionally or by name (keyword argument).
        All positional arguments must come before any keyword argument and
        vice-versa. Arguments are separated by commas.

        A positional argument simply consists of an expression (see :func:`expression`)

        A keyword argument consists of and identifier, followed by the equal `=`
        token and an expression (see :func:`expression`).

        Args:
            callee (Expr): the callee expression

        Raises:
            ParsingError: if a positional argument is passed after a keyword
                argument or if a keyword argument's name is invalid (i.e. not
                an identifier)

        Returns:
            Expr: the parsed call expression
        """
        pos_args: list[Expr] = []
        kw_args: dict[str, Expr] = {}
        keywords: bool = False
        while not self.check(TokenType.RIGHT_PAREN):
            if self.check_identifier() and self.check_next(TokenType.EQUAL):
                keywords = True
                keyword: Token = self.advance()
                self.advance()
                value: Expr = self.expression()
                name: str = keyword.lexeme
                if name in kw_args:
                    self.error(
                        self.peek(),
                        f"Multiple values passed for '{name}', only the last occurrence will be used",
                    )
                kw_args[name] = value
            else:
                value = self.expression()
                if self.check(TokenType.EQUAL):
                    error_msg: str
                    if keywords:
                        error_msg = "Invalid keyword argument name"
                    else:
                        error_msg = (
                            "Cannot pass positional arguments after a keyword argument"
                        )
                    raise self.error(self.peek(), error_msg)
                pos_args.append(value)

            if not self.match(TokenType.COMMA):
                break

        r_paren: Token = self.consume(
            TokenType.RIGHT_PAREN, "Expected ')' after arguments."
        )
        return CallExpr(
            location=Location.span(callee.location, r_paren.get_location()),
            callee=callee,
            arguments=pos_args,
            keywords=kw_args,
        )

    def reference(self) -> Expr:
        """Parse a reference expression

        A reference consists of a primary expression (see :func:`primary`)
        optionally followed by zero or more attribute accesses.

        An attribute access consists of a dot `.` token followed by an identifier

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

        This includes literals (booleans, numbers, etc.), wildcards, identifiers
        and grouped expressions

        Raises:
            ParsingError: if a primary expressions cannot be parsed from the
                following tokens

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

        if self.match(TokenType.STRING):
            return LiteralExpr(location=token.get_location(), value=token.value)

        if self.match_identifier():
            return VariableExpr(location=token.get_location(), name=token)

        if self.match(TokenType.UNDERSCORE):
            return WildcardExpr(location=token.get_location(), token=token)

        if self.match(TokenType.LEFT_PAREN):
            expr: Expr = self.expression()
            right: Token = self.consume(TokenType.RIGHT_PAREN, "Unclosed parenthesis")
            return GroupingExpr(location=token.location_to(right), expr=expr)

        raise self.error(self.peek(), "Expected expression")

    def consume_identifier(self, message: str = "Expected identifier") -> Token:
        """Consume the current token if it is a valid identifier or raise an error (see :func:`check_identifier`)

        If the current token is not a valid identifier, an error is raised
        with the provided message

        Args:
            message (str, optional): the error message. Defaults to "Expected identifier".

        Raises:
            ParsingError: if the current token is not a valid identifier

        Returns:
            Token: the current token which is a valid identifier
        """
        if not self.match_identifier():
            raise self.error(self.peek(), message)
        return self.previous()

    def match_identifier(self) -> bool:
        """Consume the next token if it is a valid identifier (see :func:`check_identifier`)

        Returns:
            bool: whether a token was matched and consumed
        """
        return self.match(TokenType.IDENTIFIER, *KEYWORDS.values())

    def check_identifier(self) -> bool:
        """Check whether the current token is a valid identifier

        A valid identifier is either an identifier token or a keyword token.
        This function always returns False if the parser is at the EOF token

        Returns:
            bool: True if the current token is a valid identifier and not EOF
        """
        for tt in [TokenType.IDENTIFIER, *KEYWORDS.values()]:
            if self.check(tt):
                return True
        return False

    def member_stmt(self) -> MemberStmt:
        """Parse a member statement

        A member statement is written consists of:
        - the `prop` (for a property) or `def` (for a method) keyword
        - an name (identifier)
        - a colon `:`
        - a type expression (see :func:`type_expr`)

        Raises:
            ParsingError: if the first token is neither `prop` nor `def`

        Returns:
            MemberStmt: the parsed member statement
        """
        kind: MemberKind
        if self.match(TokenType.PROP):
            kind = MemberKind.PROPERTY
        elif self.match(TokenType.DEF):
            kind = MemberKind.METHOD
        else:
            raise self.error(self.peek(), "Expected 'prop' or 'def'")

        name: Token = self.consume_identifier("Expected member name")
        self.consume(TokenType.COLON, "Expected ':' after member name")

        type: Type = self.type_expr()
        return MemberStmt(
            location=name.location_to(self.previous()),
            name=name,
            type=type,
            kind=kind,
        )

    def extend_declaration(self) -> ExtendStmt:
        """Parse an extension definition

        An extension statement consists of:
        - the `extend` keyword
        - a type name (identifier)
        - (optional) type parameters (see :func:`type_params`)
        - an opening brace `{`
        - zero or more member statements (see :func:`member_stmt`)
        - a closing brace `}`

        Returns:
            ExtendStmt: the parsed extension statement
        """
        keyword: Token = self.previous()
        name: Token = self.consume_identifier("Expected type name")
        params: list[TypeParam] = self.type_params()

        self.consume(TokenType.LEFT_BRACE, "Expected '{' to start extend body")
        members: list[MemberStmt] = []
        while not self.is_at_end() and not self.check(TokenType.RIGHT_BRACE):
            members.append(self.member_stmt())
        self.consume(TokenType.RIGHT_BRACE, "Unclosed extend body")
        location: Location = keyword.location_to(self.previous())
        return ExtendStmt(
            location=location,
            name=name,
            params=params,
            members=members,
        )

    def predicate_declaration(self) -> PredicateStmt:
        """Parse a predicate declaration

        A predicate statement consists of:
        - the `predicate` keyword
        - a name (identifier)
        - (optional) zero or more parameter specs (see :func:`function_params`)
        - an equal sign `=`
        - a body, a constraint expression (see :func:`constraint`)

        Returns:
            PredicateStmt: the parsed predicate declaration statement
        """
        keyword: Token = self.previous()

        name: Token = self.consume_identifier("Expected predicate name")

        params: list[ParamSpec] = []
        while self.check(TokenType.LEFT_PAREN):
            params.append(self.function_params())

        self.consume(TokenType.EQUAL, "Expected '=' after predicate subject")
        body: Expr = self.constraint()
        return PredicateStmt(
            location=keyword.location_to(self.previous()),
            name=name,
            params=params,
            body=body,
        )

    def function(self) -> FunctionType:
        """Parse a function type expression

        A function consists of:
        - the `fn` keyword
        - a parameter spec (see :func:`function_params`)
        - the arrow keyword `->`
        - a result type expression (see :func:`type_expr`)

        Returns:
            FunctionType: the parsed function type expression
        """
        params: ParamSpec = self.function_params()

        self.consume(TokenType.ARROW, "Expected '->' before result type")
        result: Type = self.type_expr()

        return FunctionType(
            location=params.l_paren.location_to(self.previous()),
            params=params,
            returns=result,
        )

    def function_params(self) -> ParamSpec:
        """Parse a parameter spec

        A parameter spec consists of zero or more comma-separated parameters,
        wrapped in parentheses.

        Like in Python, it can contain positional-only, mixed and keyword-only
        parameters (separated by `/` and `*`).

        Each parameter has a type (see :func:`type_expr`),
        preceded by a name (identifier) and a colon `:` (not required for
        positional-only parameters).

        Returns:
            ParamSpec: the parsed parameter spec
        """
        l_paren: Token = self.consume(
            TokenType.LEFT_PAREN, "Expected '(' before function parameters"
        )
        pos: list[FunctionType.Parameter] = []
        mixed: list[FunctionType.Parameter] = []
        kw: list[FunctionType.Parameter] = []

        mixed_first_tokens: list[Token] = []

        section: int = 0
        while not self.is_at_end() and not self.check(TokenType.RIGHT_PAREN):
            match section:
                case 0 if self.match(TokenType.SLASH):
                    pos = mixed
                    mixed = []
                    mixed_first_tokens = []
                    section = 1
                case 0 | 1 if self.match(TokenType.STAR):
                    section = 2
                case _:
                    # Record first token of mixed parameters for errors if unnamed
                    if section != 2:
                        mixed_first_tokens.append(self.peek())

                    name: Optional[Token] = None
                    if section == 2:
                        name = self.consume_identifier(
                            "Expected keyword parameter name"
                        )
                        self.consume(
                            TokenType.COLON, "Expected ':' after parameter name"
                        )
                    elif self.check_identifier() and self.check_next(TokenType.COLON):
                        name = self.advance()
                        self.advance()

                    type: Type = self.type_expr()
                    optional: bool = self.match(TokenType.QMARK)
                    param = FunctionType.Parameter(
                        location=None,
                        name=name,
                        type=type,
                        required=not optional,
                    )
                    if section == 2:
                        kw.append(param)
                    else:
                        mixed.append(param)

            if not self.match(TokenType.COMMA):
                break

        for param, token in zip(mixed, mixed_first_tokens):
            if param.name is None:
                # Not raised because we can keep parsing
                self.error(token, "Unnamed mixed parameter")

        self.consume(TokenType.RIGHT_PAREN, "Expected ')' after function parameters")
        return ParamSpec(l_paren=l_paren, pos=pos, mixed=mixed, kw=kw)
