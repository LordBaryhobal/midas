import ast
from typing import Optional, TextIO

import click

from midas.ast.printer import PythonAstPrinter
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
    else:
        dump = ast.dump(tree, indent=4)

    if output is None:
        click.echo(dump)
    else:
        output.write(dump)
