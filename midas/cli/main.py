import logging

import click

from midas.cli import commands


@click.group()
@click.option("-v", "--verbose", is_flag=True)
def midas(verbose: bool):
    logging.basicConfig(level=logging.DEBUG if verbose else logging.WARN)


midas.add_command(commands.check)
midas.add_command(commands.compile)
midas.add_command(commands.format)
midas.add_command(commands.highlight)
midas.add_command(commands.parse)
midas.add_command(commands.dump_registry)
midas.add_command(commands.types)
midas.add_command(commands.stubs)
midas.add_command(commands.validate)


if __name__ == "__main__":
    midas()
