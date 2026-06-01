def valid(a: int, b: int) -> int:
    return a + b

def with_if(a: int, b: int) -> int:
    if a < b:
        return b - a
    else:
        return a - b

def unreachable1():
    return
    a = 0

def unreachable2(a: int) -> int:
    if a > 10:
        return a - 10
    else:
        return a
    b = 0

def mixed(a: int, b: int):
    if a < b:
        return b - a
    else:
        return "oops"
