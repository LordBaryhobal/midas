import ast
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, TextIO

import click

import midas.ast.midas as m
import midas.ast.python as p
from midas.ast.location import Location
from midas.ast.printer import PythonAstPrinter
from midas.checker.checker import Checker
from midas.cli.highlighter import Highlighter, MidasHighlighter, PythonHighlighter
from midas.lexer.midas import MidasLexer
from midas.lexer.token import Token, TokenType
from midas.parser.midas import MidasParser
from midas.parser.python import PythonParser
from midas.resolver.resolver import Resolver


@click.group()
def midas():
    click.echo("Welcome to Midas!")


@midas.command()
@click.argument("file", type=click.File("r"))
def compile(file: TextIO):
    logging.basicConfig(level=logging.DEBUG)
    source: str = file.read()
    tree: ast.Module = ast.parse(source, filename=file.name)
    parser = PythonParser()
    stmts: list[p.Stmt] = parser.parse_module(tree)
    resolver = Resolver()
    resolver.resolve(*stmts)
    checker = Checker(resolver.locals, base_dir=Path(file.name).resolve().parent)
    checker.check(stmts)


@midas.group()
def utils():
    pass


@utils.command()
@click.option("-o", "--output", type=click.File("w"))
@click.option("-p", "--parse", is_flag=True)
@click.argument("file", type=click.File("r"))
def dump_ast(output: Optional[TextIO], parse: bool, file: TextIO):
    source: str = file.read()
    tree: ast.Module = ast.parse(source, filename=file.name)
    dump: str

    if parse:
        parser = PythonParser()
        stmts: list[p.Stmt] = parser.parse_module(tree)
        printer = PythonAstPrinter()
        dump = ""
        for stmt in stmts:
            dump += printer.print(stmt)
            dump += "\n"

    else:
        dump = ast.dump(tree, indent=4)

    if output is None:
        click.echo(dump)
    else:
        output.write(dump)


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

    @dataclass(frozen=True)
    class LocatableToken:
        token: Token

        @property
        def location(self) -> Location:
            return self.token.get_location()

    for stmt in stmts:
        highlighter.highlight(stmt)
    for token in tokens:
        if token.type == TokenType.COMMENT:
            highlighter.wrap(LocatableToken(token), "comment")
        elif token.is_keyword:
            highlighter.wrap(LocatableToken(token), "keyword")
    return highlighter


@utils.command()
@click.option("-o", "--output", type=click.File("w"), default="-")
@click.argument("file", type=click.File("r"))
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


if __name__ == "__main__":
    midas()
