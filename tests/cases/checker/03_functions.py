def foo(a: int, /, b: float, *, c: str):
    return True


r1 = foo()
r2 = foo(1)
r3 = foo(1, 2.0)
r4 = foo(1, b=2.0)
r5 = foo(1, 2.0, "test")
r6 = foo(1, 2.0, b=3.0)
r7 = foo(a=1)
r8 = foo(g="test")

r9a = foo(1, 2.0, c="test")
r9b = foo(1, b=2.0, c="test")
r9c = foo(1, c="test", b=2.0)

r10 = foo("a", 3, c=False)
