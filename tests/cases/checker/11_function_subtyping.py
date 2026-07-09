def a1(param: int) -> float: ...
def a2(param: float) -> int: ...


a = a1
a = a2


def b1(a: int, /) -> float: ...
def b2(b: float, /) -> int: ...


b = b1
b = b2


def c1(a: int) -> None: ...
def c2(p: float = 0, /, *, a: float = 0) -> None: ...


c = c1
c = c2

# Invalid subtypes


def d1(a: int) -> float: ...
def d2(a: str) -> float: ...
def d3(a: int) -> str: ...


d = d1
d = d2
d = d3


def e1(*, a: int = 0) -> None: ...
def e2(*, a: int) -> None: ...
def e3(*, a: int = 0, b: int) -> None: ...


e = e1
e = e2
e = e3
