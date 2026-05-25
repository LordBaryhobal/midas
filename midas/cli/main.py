import ast
from typing import Optional, TextIO

import click

from midas.ast.location import Location
import midas.ast.midas as m
from midas.ast.printer import PythonAstPrinter
from midas.cli.highlighter import Highlighter, MidasHighlighter, PythonHighlighter
from midas.lexer.midas import MidasLexer
from midas.lexer.token import Token, TokenType
from midas.parser.midas import MidasParser
from midas.parser.python import PythonParser


@click.group()
def midas():
    click.echo("Welcome to Midas!")


@midas.command()
@click.argument("file", type=click.File("r"))
def compile(file: TextIO):
    raise NotImplementedError


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
        parser.visit(tree)
        printer = PythonAstPrinter()
        dump = ""
        for name, annotation in parser.annotations:
            dump += f"{name} = "
            if annotation is None:
                dump += "None"
            else:
                dump += printer.print(annotation)
            dump += "\n"

        dump += "\n# Functions\n\n"

        for func in parser.functions:
            dump += printer.print(func) + "\n"
    else:
        dump = ast.dump(tree, indent=4)

    if output is None:
        click.echo(dump)
    else:
        output.write(dump)


def highlight_python(source: str, path: str) -> Highlighter:
    tree: ast.Module = ast.parse(source, filename=path)
    parser = PythonParser()
    parser.visit(tree)
    highlighter = PythonHighlighter(source)
    for _, annotation in parser.annotations:
        if annotation is not None:
            highlighter.highlight(annotation)
    for func in parser.functions:
        highlighter.highlight(func)
    return highlighter


def highlight_midas(source: str, path: str) -> Highlighter:
    lexer = MidasLexer(source, file=path)
    tokens: list[Token] = lexer.process()
    parser = MidasParser(tokens)
    stmts: list[m.Stmt] = parser.parse()
    highlighter = MidasHighlighter(source)

    class LocatableToken:
        def __init__(self, token: Token):
            self.token: Token = token

        @property
        def location(self) -> Location:
            return self.token.get_location()

    for token in tokens:
        if token.type == TokenType.COMMENT:
            highlighter.wrap(LocatableToken(token), "comment")
    for stmt in stmts:
        highlighter.highlight(stmt)
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
