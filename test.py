import importlib

from lexer.annotations import AnnotationLexer
from lexer.token import Token


mod = importlib.import_module("examples.00_syntax_prototype.01_simple_types")

annotation: str = mod.__annotations__["df"]
lexer: AnnotationLexer = AnnotationLexer(annotation, "01_simple_types.py")
tokens: list[Token] = lexer.process()
print([
    f"{t.type.name}('{t.lexeme}')"
    for t in tokens
])