def incr(value: int):
    return value + 1


def decr(value: int):
    return value - 1


def foo(a: int, /, b: float, *, c: str):
    return True


r1 = foo()  # foo() missing 2 required positional arguments: 'a' and 'b'
r2 = foo(1)  # foo() missing 1 required positional argument: 'b'
r3 = foo(1, 2.0)  # foo() missing 1 required keyword-only argument: 'c'
r4 = foo(1, b=2.0)  # foo() missing 1 required keyword-only argument: 'c'
r5 = foo(1, 2.0, "test")  # foo() takes 2 positional arguments but 3 were given
r6 = foo(1, 2.0, b=3.0)  # foo() got multiple values for argument 'b'
r7 = foo(
    a=1
)  # foo() got some positional-only arguments passed as keyword arguments: 'a'
r8 = foo(g="test")  # foo() got an unexpected keyword argument 'g'

r9a = foo(1, 2.0, c="test")
r9b = foo(1, b=2.0, c="test")
r9c = foo(1, c="test", b=2.0)

r10 = foo("a", 3, c=False)  # wrong argument types
