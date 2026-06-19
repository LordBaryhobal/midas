from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any

from midas.ast.location import Location
from midas.lexer.position import Position


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
    ARROW = auto()
    AND = auto()
    QMARK = auto()
    DOT = auto()

    # Operators
    # PLUS = auto()
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
    STRING = auto()

    # Keywords
    TYPE = auto()
    PREDICATE = auto()
    EXTEND = auto()
    WHERE = auto()
    PROP = auto()
    DEF = auto()
    FUNC = auto()

    # Misc
    COMMENT = auto()
    WHITESPACE = auto()
    EOF = auto()
    NEWLINE = auto()


KEYWORDS: dict[str, TokenType] = {
    "type": TokenType.TYPE,
    "predicate": TokenType.PREDICATE,
    "extend": TokenType.EXTEND,
    "where": TokenType.WHERE,
    "true": TokenType.TRUE,
    "false": TokenType.FALSE,
    "none": TokenType.NONE,
    "prop": TokenType.PROP,
    "def": TokenType.DEF,
    "fn": TokenType.FUNC,
}


@dataclass(frozen=True)
class Token:
    """A scanned token"""

    type: TokenType
    lexeme: str
    value: Any
    position: Position

    def get_location(self) -> Location:
        lineno: int = self.position.line
        col_offset: int = self.position.column - 1
        end_lineno = lineno
        end_col_offset = col_offset
        for c in self.lexeme:
            end_col_offset += 1
            if c == "\n":
                end_lineno += 1
                end_col_offset = 0
        return Location(
            lineno=lineno,
            col_offset=col_offset,
            end_lineno=end_lineno,
            end_col_offset=end_col_offset,
        )

    def location_to(self, to: Token) -> Location:
        return Location.span(self.get_location(), to.get_location())

    @property
    def is_keyword(self) -> bool:
        return self.lexeme in KEYWORDS
