import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from midas.ast.midas import Stmt
from midas.lexer.base import MidasSyntaxError
from midas.lexer.midas import MidasLexer
from midas.lexer.token import Token
from midas.parser.midas import MidasParser
from tests.base import Tester
from tests.serializer.midas import MidasAstJsonSerializer


@dataclass
class CaseResult:
    tokens: Optional[list[dict]] = None
    stmts: Optional[list[dict]] = None
    errors: list[dict] = field(default_factory=list)

    def dumps(self) -> str:
        return json.dumps(asdict(self), indent=2)


class MidasTester(Tester):
    @property
    def namespace(self) -> str:
        return "midas-parser"

    def _list_tests(self) -> list[Path]:
        return list(self.base_dir.rglob("*.midas"))

    def _exec_case(self, path: Path) -> CaseResult:
        if not path.exists():
            raise FileNotFoundError(f"Could not find test '{path}'")
        if not path.is_file():
            raise TypeError(f"Test '{path}' is not a file")

        result: CaseResult = CaseResult()
        content: str = path.read_text()
        lexer: MidasLexer = MidasLexer(content)
        tokens: list[Token] = []
        try:
            tokens = lexer.process()
            result.tokens = [
                {
                    "type": token.type.name,
                    "lexeme": token.lexeme,
                    "line": token.position.line,
                    "column": token.position.column,
                }
                for token in tokens
            ]
        except MidasSyntaxError as e:
            result.errors.append(
                {
                    "type": "SyntaxError",
                    "line": e.pos.line,
                    "column": e.pos.column,
                    "message": e.message,
                }
            )
            return result

        parser: MidasParser = MidasParser(tokens)
        stmts: list[Stmt] = parser.parse()
        result.stmts = MidasAstJsonSerializer().serialize(stmts)
        result.errors.extend(
            [
                {
                    "line": e.token.position.line,
                    "column": e.token.position.column,
                    "message": e.message,
                }
                for e in parser.errors
            ]
        )
        return result


if __name__ == "__main__":
    MidasTester.main()
