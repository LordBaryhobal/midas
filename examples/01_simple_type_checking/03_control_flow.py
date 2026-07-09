# Return types must have a LUB
# Valid
def minimum(x: int, y: int):
    if x < y:
        return x
    else:
        return y


# Invalid
def func(a: int):
    if a < 5:
        return "Oops"
    return True


a = 15
b = 72
c = minimum(a, b)


# Recursive but typable thanks to return hint
def factorial(n: int) -> int:
    if n <= 1:
        return 1
    return n * factorial(n - 1)


# Branches must be of the same type
category = "Category 1" if a < 10 else "Category 2"  # Valid
category = "Category 1" if a < 10 else 3  # Invalid


def foo() -> None:
    pass
