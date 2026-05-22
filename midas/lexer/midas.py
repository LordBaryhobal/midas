from midas.lexer.base import Lexer
from midas.lexer.keyword import KEYWORDS
from midas.lexer.token import TokenType


class MidasLexer(Lexer):
    def scan_token(self) -> None:
        char: str = self.advance()
        match char:
            case "(":
                self.add_token(TokenType.LEFT_PAREN)
            case ")":
                self.add_token(TokenType.RIGHT_PAREN)
            case "[":
                self.add_token(TokenType.LEFT_BRACKET)
            case "]":
                self.add_token(TokenType.RIGHT_BRACKET)
            case "{":
                self.add_token(TokenType.LEFT_BRACE)
            case "}":
                self.add_token(TokenType.RIGHT_BRACE)
            case "<":
                self.add_token(
                    TokenType.LESS_EQUAL if self.match("=") else TokenType.LESS
                )
            case ">":
                self.add_token(
                    TokenType.GREATER_EQUAL if self.match("=") else TokenType.GREATER
                )
            case "=":
                self.add_token(
                    TokenType.EQUAL_EQUAL if self.match("=") else TokenType.EQUAL
                )
            case "!" if self.match("="):
                self.add_token(TokenType.BANG_EQUAL)
            case ":":
                self.add_token(TokenType.COLON)
            case ".":
                self.add_token(TokenType.DOT)
            case "&":
                self.add_token(TokenType.AND)
            case "?":
                self.add_token(TokenType.QMARK)
            # case ",":
            #     self.add_token(TokenType.COMMA)
            case "_" if not self.is_identifier_char(self.peek_next(), start=False):
                self.add_token(TokenType.UNDERSCORE)
            case "-" if self.match(">"):
                self.add_token(TokenType.ARROW)
            # case "+":
            #     self.add_token(TokenType.PLUS)
            case "-":
                self.add_token(TokenType.MINUS)
            # case "*":
            #     self.add_token(TokenType.STAR)
            case "/" if self.match("/"):
                self.scan_comment()
            case "/" if self.match("*"):
                self.scan_comment_multiline()
            case "\n":
                self.add_token(TokenType.NEWLINE)
            case " " | "\r" | "\t":
                # Consume all whitespace characters until EOL or EOF
                while (
                    self.peek().isspace()
                    and self.peek() != "\n"
                    and not self.is_at_end()
                ):
                    self.advance()
                self.add_token(TokenType.WHITESPACE)
            case _:
                if char.isdigit():
                    self.scan_number()
                elif self.is_identifier_char(char, start=True):
                    self.scan_identifier()
                else:
                    self.error("Unexpected character")
        return None

    def scan_number(self):
        """Scan the rest of number and add it as a token

        This method handles both simple integers and floats. Scientific notation
        and base prefixes (0x, 0b, 0o) are not supported
        """
        while self.peek().isdigit():
            self.advance()

        if self.peek() == "." and self.peek_next().isdigit():
            self.advance()
            while self.peek().isdigit():
                self.advance()

        value: float = float(self.source[self.start : self.idx])
        self.add_token(TokenType.NUMBER, value)

    def scan_identifier(self):
        """Scan the rest of an identifier and add it as a token

        An identifier starts with a letter, followed by any number of
        alphanumerical characters or underscores
        """
        while self.is_identifier_char(self.peek(), start=False):
            self.advance()

        lexeme: str = self.source[self.start : self.idx]
        token_type: TokenType = KEYWORDS.get(lexeme, TokenType.IDENTIFIER)
        self.add_token(token_type)

    def scan_comment(self):
        """Scan the rest of a comment and add it as a token

        A comment starts with `//` and ends at the EOL/EOF
        """
        while self.peek() != "\n" and not self.is_at_end():
            self.advance()
        self.add_token(TokenType.COMMENT)

    def scan_comment_multiline(self):
        """Scan the rest of a multiline comment and add it as a token

        A multiline comment starts with `/*` and ends with `*/` or at the EOF
        """
        while (
            not (self.peek() == "*" and self.peek_next() == "/")
            and not self.is_at_end()
        ):
            self.advance()
        if not self.is_at_end():
            self.advance()
        if not self.is_at_end():
            self.advance()
        self.add_token(TokenType.COMMENT)

    def is_identifier_char(self, char: str, *, start: bool) -> bool:
        if char == "_":
            return True
        if char.isalpha():
            return True
        if not start and char.isdigit():
            return True
        return False
