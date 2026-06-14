class Ansi:
    CTRL = "\x1b["
    RESET = CTRL + "0m"
    BOLD = CTRL + "1m"
    DIM = CTRL + "2m"
    ITALIC = CTRL + "3m"
    UNDERLINE = CTRL + "4m"

    BLACK = 0
    RED = 1
    GREEN = 2
    YELLOW = 3
    BLUE = 4
    MAGENTA = 5
    CYAN = 6
    WHITE = 7

    BRIGHT_BLACK = 60
    BRIGHT_RED = 61
    BRIGHT_GREEN = 62
    BRIGHT_YELLOW = 63
    BRIGHT_BLUE = 64
    BRIGHT_MAGENTA = 65
    BRIGHT_CYAN = 66
    BRIGHT_WHITE = 67

    @classmethod
    def FG(cls, col: int) -> str:
        return f"{cls.CTRL}{30 + col}m"

    @classmethod
    def BG(cls, col: int) -> str:
        return f"{cls.CTRL}{40 + col}m"

    @classmethod
    def FG_RGB(cls, r: int, g: int, b: int) -> str:
        return f"{cls.CTRL}38;2;{r};{g};{b}m"

    @classmethod
    def BG_RGB(cls, r: int, g: int, b: int) -> str:
        return f"{cls.CTRL}48;2;{r};{g};{b}m"
