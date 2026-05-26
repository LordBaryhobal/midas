import json
from pathlib import Path

from midas.ast.printer import MidasAstPrinter
from midas.lexer.midas import MidasLexer
from midas.lexer.token import Token
from midas.parser.midas import MidasParser


def test_midas():
    # Midas type definitions
    path: Path = Path("examples") / "00_syntax_prototype" / "03_custom_types_v2.midas"
    definitions: str = path.read_text()
    midas_lexer: MidasLexer = MidasLexer(definitions, path.name)
    tokens: list[Token] = midas_lexer.process()
    # print([f"{t.type.name}('{t.lexeme}')" for t in tokens])
    with open("tokens.json", "w") as f:
        json.dump([f"{t.type.name}('{t.lexeme}')" for t in tokens], f, indent=4)

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
