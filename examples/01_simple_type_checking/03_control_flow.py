def minimum(x: int, y: int):
    if x < y:
        return x
    else:
        return y

a = 15
b = 72
c = minimum(a, b)

def factorial(n: int) -> int:
    if n <= 1:
        return 1
    return n * factorial(n - 1)

category = "Category 1" if a < 10 else "Category 2"