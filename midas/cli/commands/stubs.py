import ast
import time
from pathlib import Path
from typing import Optional, TextIO

import black
import click
from watchdog.events import DirModifiedEvent, FileModifiedEvent, FileSystemEventHandler
from watchdog.observers import Observer

from midas.checker.checker import TypeChecker
from midas.generator.stubs import StubsGenerator


def generate_stubs(in_path: Path, out_path: Path):
    checker = TypeChecker()
    checker.import_midas(in_path)

    generator = StubsGenerator(checker.types)
    module: ast.Module = generator.generate_stubs()
    module = ast.fix_missing_locations(module)

    output: str = ast.unparse(module)
    output = black.format_str(output, mode=black.Mode(is_pyi=True))

    out_path.write_text(output)


class Handler(FileSystemEventHandler):
    def __init__(self, in_path: Path, out_path: Path) -> None:
        super().__init__()
        self.in_path: Path = in_path
        self.out_path: Path = out_path

    def on_modified(self, event: DirModifiedEvent | FileModifiedEvent) -> None:
        generate_stubs(self.in_path, self.out_path)


@click.command(help="Generate stubs from Midas definitions")
@click.argument("file", type=click.File("r"))
@click.option("-o", "--output", type=click.File("w"))
@click.option("-w", "--watch", is_flag=True)
def stubs(
    file: TextIO,
    output: Optional[TextIO],
    watch: bool,
):
    source_path: Path = Path(file.name).resolve()
    out_path: Path = source_path.with_suffix(".pyi")
    if output is not None:
        out_path = Path(output.name).resolve()
    generate_stubs(source_path, out_path)

    if watch:
        print(f"Watching {source_path}...")
        print("Press CTRL+C to stop")
        handler = Handler(source_path, out_path)
        observer = Observer()
        observer.schedule(handler, str(source_path))
        observer.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()
