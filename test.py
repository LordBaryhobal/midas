import importlib
from pathlib import Path

from core.ast.printer import AnnotationAstPrinter, MidasAstPrinter
from lexer.annotations import AnnotationLexer
from lexer.midas import MidasLexer
from lexer.token import Token
from parser.annotations import AnnotationParser
from parser.midas import MidasParser


def test_annotation():
    # Frame annotation
    mod = importlib.import_module("examples.00_syntax_prototype.01_simple_types")

    annotation: str = mod.__annotations__["df"]
    lexer: AnnotationLexer = AnnotationLexer(annotation, "01_simple_types.py")
    tokens: list[Token] = lexer.process()
    # print([f"{t.type.name}('{t.lexeme}')" for t in tokens])

    parser = AnnotationParser(tokens)
    parsed = parser.parse()
    print(parsed)
    for err in parser.errors:
        print(err.get_report())
    printer = AnnotationAstPrinter()
    if parsed is not None:
        print(printer.print(parsed))


def test_midas():
    # Midas type definitions
    path: Path = Path("examples") / "00_syntax_prototype" / "02_custom_types.midas"
    definitions: str = path.read_text()
    midas_lexer: MidasLexer = MidasLexer(definitions, path.name)
    tokens: list[Token] = midas_lexer.process()
    # print([f"{t.type.name}('{t.lexeme}')" for t in tokens])

    parser = MidasParser(tokens)
    parsed = parser.parse()
    print(parsed)
    for err in parser.errors:
        print(err.get_report())
    printer = MidasAstPrinter()
    for stmt in parsed:
        if stmt is None:
            print("None")
            continue
        print(printer.print(stmt))


test_midas()
