import importlib
from pathlib import Path

from lexer.annotations import AnnotationLexer
from lexer.midas import MidasLexer
from lexer.token import Token


# Frame annotation
mod = importlib.import_module("examples.00_syntax_prototype.01_simple_types")

annotation: str = mod.__annotations__["df"]
lexer: AnnotationLexer = AnnotationLexer(annotation, "01_simple_types.py")
tokens: list[Token] = lexer.process()
print([
    f"{t.type.name}('{t.lexeme}')"
    for t in tokens
])

# Midas type definitions
path: Path = Path("examples") / "00_syntax_prototype" / "02_custom_types.midas"
definitions: str = path.read_text()
midas_lexer: MidasLexer = MidasLexer(definitions, path.name)
tokens = midas_lexer.process()
print([
    f"{t.type.name}('{t.lexeme}')"
    for t in tokens
])
