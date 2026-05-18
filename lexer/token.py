from dataclasses import dataclass
from enum import Enum, auto
from typing import Any

from lexer.position import Position


class TokenType(Enum):
    # Punctuation
    LEFT_PAREN = auto()
    RIGHT_PAREN = auto()
    LEFT_BRACKET = auto()
    RIGHT_BRACKET = auto()
    LEFT_BRACE = auto()
    RIGHT_BRACE = auto()
    COLON = auto()
    COMMA = auto()
    UNDERSCORE = auto()

    # Operators
    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    SLASH = auto()
    GREATER = auto()
    GREATER_EQUAL = auto()
    LESS = auto()
    LESS_EQUAL = auto()
    EQUAL = auto()
    EQUAL_EQUAL = auto()
    BANG_EQUAL = auto()

    # Literals
    IDENTIFIER = auto()
    NUMBER = auto()
    TRUE = auto()
    FALSE = auto()
    NONE = auto()

    # Keywords
    TYPE = auto()
    OP = auto()
    CONSTRAINT = auto()

    # Misc
    COMMENT = auto()
    WHITESPACE = auto()
    EOF = auto()
    NEWLINE = auto()


@dataclass(frozen=True)
class Token:
    """A scanned token"""

    type: TokenType
    lexeme: str
    value: Any
    position: Position
