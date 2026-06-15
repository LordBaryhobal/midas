import ast
from typing import TextIO

import click

import midas.ast.midas as m
import midas.ast.python as p
from midas.cli.highlighter import (
    Highlighter,
    LocatableToken,
    MidasHighlighter,
    PythonHighlighter,
)
from midas.lexer.midas import MidasLexer
from midas.lexer.token import Token, TokenType
from midas.parser.midas import MidasParser
from midas.parser.python import PythonParser


def highlight_python(source: str, path: str) -> Highlighter:
    tree: ast.Module = ast.parse(source, filename=path)
    parser = PythonParser()
    stmts: list[p.Stmt] = parser.parse_module(tree)
    highlighter = PythonHighlighter(source)
    for stmt in stmts:
        highlighter.highlight(stmt)
    return highlighter


def highlight_midas(source: str, path: str) -> Highlighter:
    lexer = MidasLexer(source, file=path)
    tokens: list[Token] = lexer.process()
    parser = MidasParser(tokens)
    stmts: list[m.Stmt] = parser.parse()
    highlighter = MidasHighlighter(source)
    for err in parser.errors:
        print(err.get_report())

    for stmt in stmts:
        highlighter.highlight(stmt)
    for token in tokens:
        if token.type == TokenType.COMMENT:
            highlighter.wrap(LocatableToken(token), "comment")
        elif token.is_keyword:
            highlighter.wrap(LocatableToken(token), "keyword")
    return highlighter


@click.command(
    help="Parse a Python or Midas file and produce a highlighted version showing AST node types inline",
    short_help="Parse and highlight a Python or Midas file",
)
@click.argument("file", type=click.File("r"))
@click.option("-o", "--output", type=click.File("w"), default="-")
def highlight(output: TextIO, file: TextIO):
    source: str = file.read()
    highlighter: Highlighter

    if file.name.endswith(".py"):
        highlighter = highlight_python(source, file.name)
    elif file.name.endswith(".midas"):
        highlighter = highlight_midas(source, file.name)
    else:
        raise ValueError("Unsupported file type")

    highlighter.dump(output)
