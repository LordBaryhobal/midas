import ast
import json
import logging
from pathlib import Path
from typing import Optional, TextIO, get_args

import click

import midas.ast.midas as m
import midas.ast.python as p
from midas.ast.location import Location
from midas.ast.printer import MidasAstPrinter, MidasPrinter, PythonAstPrinter
from midas.checker.checker import Checker
from midas.checker.diagnostic import Diagnostic, DiagnosticType
from midas.checker.types import Type
from midas.cli.ansi import Ansi
from midas.cli.highlighter import (
    DiagnosticsHighlighter,
    Highlighter,
    LocatableToken,
    MidasHighlighter,
    PythonHighlighter,
)
from midas.lexer.midas import MidasLexer
from midas.lexer.token import Token, TokenType
from midas.parser.midas import MidasParser
from midas.parser.python import PythonParser
from midas.resolver.resolver import Resolver
from midas.utils import UniversalJSONDumper


@click.group()
def midas():
    pass


def print_diagnostic(lines: list[str], diagnostic: Diagnostic, indent: int = 4):
    """Pretty-print a diagnostic, showing some context if possible

    If the diagnostic concerns a specific part of one line, the line is shown
    with the affected part highlighted. The message is clearly printed under the
    line with an underline further indicating the target expression.

    If multiple lines are concerned, no context is shown, only the
    diagnostic type, location and message

    Args:
        lines (list[str]): source code lines
        diagnostic (Diagnostic): the diagnostic to print
        indent (int, optional): the number of spaces added before the target line to indent if from the location header. Defaults to 4.
    """

    loc: Location = diagnostic.location
    if loc.lineno != loc.end_lineno:
        print(diagnostic)
        return

    start_offset: int = loc.col_offset
    end_offset: int = loc.end_col_offset or (start_offset + 1)

    line: str = lines[loc.lineno - 1]
    before: str = line[:start_offset]
    after: str = line[end_offset:]

    color: int = {
        DiagnosticType.ERROR: Ansi.RED,
        DiagnosticType.WARNING: Ansi.YELLOW,
        DiagnosticType.INFO: Ansi.CYAN,
    }.get(diagnostic.type, Ansi.WHITE)

    subject: str = Ansi.FG(color) + line[start_offset:end_offset] + Ansi.RESET
    cursor: str = (
        " " * start_offset
        + Ansi.FG(color)
        + "~" * (end_offset - start_offset)
        + "> "
        + diagnostic.message
        + Ansi.RESET
    )

    indent_str: str = " " * indent
    print(diagnostic.location_str + ":")
    print(indent_str + before + subject + after)
    print(indent_str + cursor)
    print()


@midas.command()
@click.option("-l", "--highlight", type=click.File("w"))
@click.option("-t", "--types", type=click.File("r"), multiple=True)
@click.option("-v", "--verbose", is_flag=True)
@click.argument("file", type=click.File("r"))
def compile(
    highlight: Optional[TextIO],
    types: tuple[TextIO],
    verbose: bool,
    file: TextIO,
):
    logging.basicConfig(level=logging.DEBUG if verbose else logging.WARN)
    source: str = file.read()
    tree: ast.Module = ast.parse(source, filename=file.name)
    parser = PythonParser()
    stmts: list[p.Stmt] = parser.parse_module(tree)
    resolver = Resolver()
    resolver.resolve(*stmts)
    types_paths: list[Path] = [Path(t.name).resolve() for t in types]
    checker = Checker(
        resolver.locals,
        source_path=Path(file.name).resolve(),
        types_paths=types_paths,
    )
    diagnostics: list[Diagnostic] = checker.check(stmts)
    lines: list[str] = source.split("\n")
    for diagnostic in diagnostics:
        print_diagnostic(lines, diagnostic)

    if verbose:
        print(
            json.dumps(
                UniversalJSONDumper.dump(
                    checker.global_env,
                    [("Environment", "_children")],
                    lambda obj: isinstance(obj, get_args(Type)),
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


@midas.command()
@click.option("-o", "--output", type=click.File("w"), default="-")
@click.argument("file", type=click.File("r"))
def format(output: TextIO, file: TextIO):
    source: str = file.read()
    printer = MidasPrinter()
    lexer = MidasLexer(source, file=file.name)
    tokens: list[Token] = lexer.process()
    parser = MidasParser(tokens)
    stmts: list[m.Stmt] = parser.parse()
    for err in parser.errors:
        print(err.get_report())
    for stmt in stmts:
        output.write(printer.print(stmt) + "\n")


if __name__ == "__main__":
    midas()
