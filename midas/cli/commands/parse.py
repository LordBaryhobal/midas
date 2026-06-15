# **Parse and pretty-print AST**
# ```shell
# midas parse <file.midas / file.py>
# ```

import ast
from typing import TextIO

import click

import midas.ast.midas as m
import midas.ast.python as p
from midas.ast.printer import MidasAstPrinter, PythonAstPrinter
from midas.lexer.midas import MidasLexer
from midas.lexer.token import Token
from midas.parser.midas import MidasParser
from midas.parser.python import PythonParser


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


@click.command()
@click.argument("file", type=click.File("r"))
@click.option("--raw", is_flag=True)
def parse(file: TextIO, raw: bool):
    source: str = file.read()

    dump: str
    if file.name.endswith(".py"):
        tree: ast.Module = ast.parse(source, filename=file.name)
        if raw:
            dump = ast.dump(tree, indent=4)
        else:
            dump = dump_python_ast(tree)
    elif file.name.endswith(".midas"):
        dump = dump_midas_ast(source, file.name)
    else:
        raise ValueError("Unsupported file type")

    click.echo(dump)
