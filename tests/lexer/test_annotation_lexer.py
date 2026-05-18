from typing import Any

import pytest

from lexer.annotations import AnnotationLexer
from lexer.token import Token, TokenType


def scan(source: str) -> list[Token]:
    return AnnotationLexer(source).process()


def assert_n_tokens(tokens: list[Token], n: int):
    assert len(tokens) == n + 1
    assert tokens[-1].type == TokenType.EOF


@pytest.mark.parametrize(
    "src,expected",
    [
        ("(", TokenType.LEFT_PAREN),
        (")", TokenType.RIGHT_PAREN),
        ("[", TokenType.LEFT_BRACKET),
        ("]", TokenType.RIGHT_BRACKET),
        (":", TokenType.COLON),
        (",", TokenType.COMMA),
        ("_", TokenType.UNDERSCORE),
    ],
)
def test_punctuation(src: str, expected: TokenType):
    tokens: list[Token] = scan(src)
    assert_n_tokens(tokens, 1)
    assert tokens[0].type == expected


@pytest.mark.parametrize(
    "src,expected",
    [
        ("+", TokenType.PLUS),
        (">", TokenType.GREATER),
        (">=", TokenType.GREATER_EQUAL),
        ("<", TokenType.LESS),
        ("<=", TokenType.LESS_EQUAL),
        ("=", TokenType.EQUAL),
        ("==", TokenType.EQUAL_EQUAL),
        ("!=", TokenType.BANG_EQUAL),
    ],
)
def test_operators(src: str, expected: TokenType):
    tokens: list[Token] = scan(src)
    assert_n_tokens(tokens, 1)
    assert tokens[0].type == expected


@pytest.mark.parametrize(
    "src,expected",
    [
        ("a", TokenType.IDENTIFIER),
        ("foo", TokenType.IDENTIFIER),
        ("foo1", TokenType.IDENTIFIER),
        ("foo_", TokenType.IDENTIFIER),
        ("foo_bar1_baz2", TokenType.IDENTIFIER),
        ("FOO_BAR1_BAZ2", TokenType.IDENTIFIER),
        ("True", TokenType.TRUE),
        ("False", TokenType.FALSE),
        ("None", TokenType.NONE),
    ],
)
def test_identifiers_keywords(src: str, expected: TokenType):
    tokens: list[Token] = scan(src)
    assert_n_tokens(tokens, 1)
    assert tokens[0].type == expected


@pytest.mark.parametrize(
    "src,expected",
    [
        ("#", TokenType.COMMENT),
        ("# This is a comment", TokenType.COMMENT),
        (" ", TokenType.WHITESPACE),
        ("\t", TokenType.WHITESPACE),
        ("\r", TokenType.WHITESPACE),
        ("  \t  \t", TokenType.WHITESPACE),
        ("\n", TokenType.NEWLINE),
    ],
)
def test_misc(src: str, expected: TokenType):
    tokens: list[Token] = scan(src)
    assert_n_tokens(tokens, 1)
    assert tokens[0].type == expected


@pytest.mark.parametrize(
    "src,expected_type,expected_value",
    [
        ("0", TokenType.NUMBER, 0),
        ("0.0", TokenType.NUMBER, 0),
        ("1234.56", TokenType.NUMBER, 1234.56),
    ],
)
def test_literals(src: str, expected_type: TokenType, expected_value: Any):
    tokens: list[Token] = scan(src)
    assert_n_tokens(tokens, 1)
    assert tokens[0].type == expected_type
    assert tokens[0].value == expected_value
