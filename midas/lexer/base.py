from abc import ABC, abstractmethod
from typing import Any, Callable, Optional

from midas.lexer.position import Position
from midas.lexer.token import Token, TokenType


class MidasSyntaxError(Exception):
    def __init__(self, pos: Position, message: str):
        super().__init__(f"[ERROR] Error at {pos}: {message}")
        self.pos: Position = pos
        self.message: str = message


class Lexer(ABC):
    """An abstract lexer which provides methods to easily extend it into a concrete one

    This implementation is based on the [_Crafting Interpreters_][1] book by Robert Nystrom,
    more specifically on my [previous Python implementation][2]

    [1]: https://craftinginterpreters.com/
    [2]: https://git.kb28.ch/HEL/pebble
    """

    def __init__(self, source: str, file: Optional[str] = None) -> None:
        """Create a new lexer to scan for tokens in the given source

        Args:
            source (str): the source to scan
            file (Optional[str], optional): the path of the given source. Can be a file path or any string identifier. Defaults to None.
        """
        self.source: str = source
        self.file: Optional[str] = file
        self.tokens: list[Token] = []
        self.start: int = 0
        self.idx: int = 0
        self.length: int = len(self.source)
        self.line: int = 1
        self.column: int = 1
        self.start_pos: Position = self.get_position()

    def error(self, msg: str):
        """Raise a syntax error

        Args:
            msg (str): the error message

        Raises:
            MidasSyntaxError
        """
        raise MidasSyntaxError(self.start_pos, msg)

    def process(self) -> list[Token]:
        """Scan tokens out of the source text

        Returns:
            list[Token]: all the tokens that could be scanned

        Raises:
            MidasSyntaxError: if a syntax error is found
        """
        self.scan_tokens()
        self.tokens.append(Token(TokenType.EOF, "", None, self.get_position()))
        return self.tokens

    def is_at_end(self) -> bool:
        """Whether the lexer is at the end of the source

        Returns:
            bool: True if the current index is at the end of the source
        """
        return self.idx >= self.length

    def get_position(self) -> Position:
        """Get the current position

        Returns:
            Position: the current position
        """
        return Position(file=self.file, line=self.line, column=self.column)

    def peek(self) -> str:
        """Get the current character without advancing, if any

        Returns:
            str: the current character, or an empty string if at EOF
        """
        if self.idx < self.length:
            return self.source[self.idx]
        return ""

    def peek_next(self) -> str:
        """Get the next character without advancing, if any

        Returns:
            str: the next character, or an empty string if at EOF
        """
        if self.idx + 1 < self.length:
            return self.source[self.idx + 1]
        return ""

    def advance(self) -> str:
        """Get the new character and advance

        Returns:
            str: the current character, before advancing
        """
        char: str = self.peek()
        self.idx += 1
        self.column += 1
        if char == "\n":
            self.newline()
        return char

    def newline(self):
        """Update the current position after encountering a newline character"""
        self.line += 1
        self.column = 1

    def match(self, expected: str) -> bool:
        """Consume the next character if it matches the given value

        Args:
            expected (str): the expected character

        Returns:
            bool: whether a character was matched and consumed
        """
        if self.peek() == expected:
            self.advance()
            return True
        return False

    def update_start(self):
        """Update the starting position of the current lexeme

        The cursor marking the start of the lexeme currently being scanned is
        moved to the current position
        """
        self.start_pos = self.get_position()
        self.start = self.idx

    def add_token(self, token_type: TokenType, value: Optional[Any] = None):
        """Add the current lexeme to the list of scanned tokens

        Args:
            token_type (TokenType): the type of token to add
            value (Optional[Any], optional): the value of the token (useful for numbers or constants). Defaults to None.
        """
        lexeme: str = self.source[self.start : self.idx]
        self.tokens.append(
            Token(position=self.start_pos, type=token_type, lexeme=lexeme, value=value)
        )

    def scan_tokens(self, condition: Optional[Callable[[], bool]] = None):
        """Scan tokens until EOF is reached or the given condition becomes False

        Args:
            condition (Optional[Callable[[], bool]], optional): the condition to continue scanning tokens.
                If None, defaults to always being True, effectively scanning tokens until EOF is reached. Defaults to None.
        """
        if condition is None:
            condition = lambda: True  # noqa: E731
        while condition() and not self.is_at_end():
            self.update_start()
            self.scan_token()

    @abstractmethod
    def scan_token(self) -> None:
        """Scan a token

        This function should (at least) consume the current character and produce the appropriate token(s), using :func:`add_token`
        """
        pass
