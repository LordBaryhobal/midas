from typing import TextIO

import click

import midas.ast.midas as m
from midas.ast.printer import MidasPrinter
from midas.lexer.midas import MidasLexer
from midas.lexer.token import Token
from midas.parser.midas import MidasParser


@click.command(help="Parse and pretty print a Midas file")
@click.argument("file", type=click.File("r"))
@click.option("-o", "--output", type=click.File("w"), default="-")
def format(file: TextIO, output: TextIO):
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
