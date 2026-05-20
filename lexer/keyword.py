from lexer.token import TokenType

KEYWORDS: dict[str, TokenType] = {
    "type": TokenType.TYPE,
    "op": TokenType.OP,
    "constraint": TokenType.CONSTRAINT,
    "true": TokenType.TRUE,
    "false": TokenType.FALSE,
    "none": TokenType.NONE,
}
