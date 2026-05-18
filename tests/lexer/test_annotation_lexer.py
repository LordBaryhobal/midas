import pytest

from lexer.annotations import AnnotationLexer
from lexer.token import Token, TokenType


def scan(source: str) -> list[Token]:
    return AnnotationLexer(source).process()

def assert_n_tokens(tokens: list[Token], n: int):
    assert len(tokens) == n + 1
    assert tokens[-1].type == TokenType.EOF

@pytest.mark.parametrize("src,expected", [
    ("(", TokenType.LEFT_PAREN),
    (")", TokenType.RIGHT_PAREN),
    ("[", TokenType.LEFT_BRACKET),
    ("]", TokenType.RIGHT_BRACKET),
    (":", TokenType.COLON),
    (",", TokenType.COMMA),
    ("_", TokenType.UNDERSCORE),
])
def test_punctuation(src: str, expected: TokenType):
    tokens: list[Token] = scan(src)
    assert_n_tokens(tokens, 1)
    assert tokens[0].type == expected