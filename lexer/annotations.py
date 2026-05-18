from lexer.base import Lexer
from lexer.token import TokenType


class AnnotationLexer(Lexer):
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
            case "!":
                if self.peek() == "=":
                    self.add_token(TokenType.BANG_EQUAL)
                else:
                    self.error("Unexpected single bang. Did you mean '!=' ?")
            case ":":
                self.add_token(TokenType.COLON)
            case ",":
                self.add_token(TokenType.COMMA)
            case "_":
                self.add_token(TokenType.UNDERSCORE)
            case "+":
                self.add_token(TokenType.PLUS)
            case "#":
                self.scan_comment()
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
                elif char.isalpha():
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
        while self.peek().isalnum() or self.peek() == "_":
            self.advance()
        self.add_token(TokenType.IDENTIFIER)

    def scan_comment(self):
        """Scan the rest of a comment and add it as a token

        A comment starts with a `#` character and ends at the EOL/EOF
        """
        while self.peek() != "\n" and not self.is_at_end():
            self.advance()
        self.add_token(TokenType.COMMENT)
