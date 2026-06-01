import ast
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, TextIO

import click

import midas.ast.midas as m
import midas.ast.python as p
from midas.ast.location import Location
from midas.ast.printer import MidasAstPrinter, PythonAstPrinter
from midas.checker.checker import Checker
from midas.checker.diagnostic import Diagnostic
from midas.cli.highlighter import DiagnosticsHighlighter, Highlighter, MidasHighlighter, PythonHighlighter
from midas.lexer.midas import MidasLexer
from midas.lexer.token import Token, TokenType
from midas.parser.midas import MidasParser
from midas.parser.python import PythonParser
from midas.resolver.resolver import Resolver
from midas.utils import UniversalJSONDumper


@click.group()
def midas():
    click.echo("Welcome to Midas!")


@midas.command()
@click.option("-l", "--highlight", type=click.File("w"))
@click.argument("file", type=click.File("r"))
def compile(highlight: Optional[TextIO], file: TextIO):
    logging.basicConfig(level=logging.DEBUG)
    source: str = file.read()
    tree: ast.Module = ast.parse(source, filename=file.name)
    parser = PythonParser()
    stmts: list[p.Stmt] = parser.parse_module(tree)
    resolver = Resolver()
    resolver.resolve(*stmts)
    checker = Checker(resolver.locals, file_path=Path(file.name).resolve())
    diagnostics: list[Diagnostic] = checker.check(stmts)
    for diagnostic in diagnostics:
        print(diagnostic)

    print(
        json.dumps(
            UniversalJSONDumper.dump(
                checker.global_env, [("Environment", "_children")]
            ),
            indent=4,
        )
    )
    if highlight is not None:
        highlighter = DiagnosticsHighlighter(source)
        highlighter.highlight(diagnostics)
        highlighter.dump(highlight)


@midas.group()
def utils():
    pass


def dump_python_ast(tree: ast.Module) -> str:
    parser = PythonParser()
    stmts: list[p.Stmt] = parser.parse_module(tree)
    printer = PythonAstPrinter()
    dump: str = ""
    for stmt in stmts:
        dump += printer.print(stmt)
        dump += "\n"
    return dump


def dump_midas_ast(source: str, filename: str) -> str:
    lexer = MidasLexer(source, file=filename)
    tokens: list[Token] = lexer.process()
    parser = MidasParser(tokens)
    stmts: list[m.Stmt] = parser.parse()
    if len(parser.errors) != 0:
        for err in parser.errors:
            print(err.get_report())
        raise RuntimeError("A parsing error occurred")
    printer = MidasAstPrinter()
    dump: str = ""
    for stmt in stmts:
        dump += printer.print(stmt)
        dump += "\n"
    return dump


@utils.command()
@click.option("-o", "--output", type=click.File("w"))
@click.option("-p", "--parse", is_flag=True)
@click.argument("file", type=click.File("r"))
def dump_ast(output: Optional[TextIO], parse: bool, file: TextIO):
    source: str = file.read()

    dump: str
    if file.name.endswith(".py"):
        tree: ast.Module = ast.parse(source, filename=file.name)
        if parse:
            dump = dump_python_ast(tree)
        else:
            dump = ast.dump(tree, indent=4)
    elif file.name.endswith(".midas"):
        dump = dump_midas_ast(source, file.name)
    else:
        raise ValueError("Unsupported file type")

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
