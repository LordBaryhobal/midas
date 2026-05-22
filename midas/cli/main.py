import ast
from typing import Optional, TextIO

import click


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
@click.argument("file", type=click.File("r"))
def dump_ast(output: Optional[TextIO], file: TextIO):
    source: str = file.read()
    tree: ast.Module = ast.parse(source, filename=file.name)
    dump: str = ast.dump(tree, indent=4)
    if output is None:
        click.echo(dump)
    else:
        output.write(dump)
