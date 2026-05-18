from lexer.token import TokenType

ANNOTATION_KEYWORDS: dict[str, TokenType] = {
    "True": TokenType.TRUE,
    "False": TokenType.FALSE,
    "None": TokenType.NONE,
}

MIDAS_KEYWORDS: dict[str, TokenType] = {
    "type": TokenType.TYPE,
    "op": TokenType.OP,
    "constraint": TokenType.CONSTRAINT,
    "true": TokenType.TRUE,
    "false": TokenType.FALSE,
    "none": TokenType.NONE,
}
