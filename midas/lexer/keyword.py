from midas.lexer.token import TokenType

KEYWORDS: dict[str, TokenType] = {
    "type": TokenType.TYPE,
    "op": TokenType.OP,
    "predicate": TokenType.PREDICATE,
    "extend": TokenType.EXTEND,
    "where": TokenType.WHERE,
    "true": TokenType.TRUE,
    "false": TokenType.FALSE,
    "none": TokenType.NONE,
}
