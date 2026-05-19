from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Generic, TypeVar

from lexer.token import Token, TokenType
from parser.errors import ParsingError


@dataclass(frozen=True)
class TokenError:
    """A parsing error linked to a particular token"""

    token: Token
    message: str

    def get_report(self) -> str:
        """Get a detailed error message

        Returns:
            str: the complete error message
        """
        where: str = f"'{self.token.lexeme}'"
        if self.token.type == TokenType.EOF:
            where = "end"
        return f"({self.token.position}) Error at {where}: {self.message}"


T = TypeVar("T")


class Parser(ABC, Generic[T]):
    """An abstract parser which provides methods to easily extend it into a concrete one

    This implementation is based on the [_Crafting Interpreters_][1] book by Robert Nystrom,
    more specifically on my [previous Python implementation](https://git.kb28.ch/HEL/pebble)

    [1]: https://craftinginterpreters.com/
    """

    IGNORE: set[TokenType] = {
        TokenType.WHITESPACE,
        TokenType.COMMENT,
        TokenType.NEWLINE,
    }

    def __init__(self, tokens: list[Token]) -> None:
        """Create a new parser to parse the given tokens

        Args:
            tokens (list[Token]): the tokens to parse
        """
        self.tokens: list[Token] = list(
            filter(lambda t: t.type not in self.IGNORE, tokens)
        )
        self.current: int = 0
        self.length: int = len(self.tokens)
        self.errors: list[TokenError] = []

    def error(self, token: Token, message: str):
        """Record an error

        Args:
            token (Token): the token at which the error was detected
            message (str): a message explaining the error

        Returns:
            ParsingError: the parsing error to raise
        """
        self.errors.append(TokenError(token=token, message=message))
        return ParsingError()

    @abstractmethod
    def parse(self) -> T:
        """Parse the tokens

        Returns:
            T: the parsed element(s)
        """
        pass

    def is_at_end(self) -> bool:
        """Whether the parser is at the end of the token list

        Returns:
            bool: True if the current index is at the end of the token list
        """
        return self.peek().type == TokenType.EOF

    def peek(self) -> Token:
        """Get the current token without advancing

        Returns:
            Token: the current token
        """
        return self.tokens[self.current]

    def previous(self) -> Token:
        """Get the previous token

        This function is unsafe and will raise an IndexError if called when
        the parser is at the begin of the token list

        Returns:
            Token: the previous token
        """
        return self.tokens[self.current - 1]

    def check(self, token_type: TokenType) -> bool:
        """Check whether the current token is of the given type

        This function always returns False if the parser is at the EOF token

        Args:
            token_type (TokenType): the type of token to check

        Returns:
            bool: True if the current token is of the given type and not EOF
        """
        if self.is_at_end():
            return False
        return self.peek().type == token_type

    def check_next(self, token_type: TokenType) -> bool:
        """Check whether the next token is of the given type

        This function always returns False if the parser is at the EOF token

        Args:
            token_type (TokenType): the type of token to check

        Returns:
            bool: True if the current token is of the given type and not EOF
        """
        if self.is_at_end():
            return False
        if self.current + 1 >= self.length:
            return False
        token: Token = self.tokens[self.current + 1]
        if token.type == TokenType.EOF:
            return False
        return token.type == token_type

    def advance(self) -> Token:
        """Consume and return the current token, if not at the EOF

        Returns:
            Token: the current token, before advancing
        """
        if not self.is_at_end():
            self.current += 1
        return self.previous()

    def match(self, *types: TokenType) -> bool:
        """Consume the next token if it matches one of the given types

        Returns:
            bool: whether a token was matched and consumed
        """
        for token_type in types:
            if self.check(token_type):
                self.advance()
                return True
        return False

    def consume(self, token_type: TokenType, error_msg: str) -> Token:
        """Consume the current token if it matches the given type or raise an error

        If the current token doesn't match the given type, an error is raised
        with the provided message

        Args:
            token_type (TokenType): the expected token type
            error_msg (str): the error message if the token doesn't match

        Raises:
            SyntaxError: if the current token doesn't match the given type

        Returns:
            Token: the current token which matched the given type
        """
        if self.check(token_type):
            return self.advance()
        raise self.error(self.peek(), error_msg)
