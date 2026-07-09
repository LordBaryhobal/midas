# type: ignore
# ruff: disable [F821]

foo = cast(Foo, object())
t1 = cast(T1, object())
t2 = cast(T2, object())

a = foo.bar(t1)
b = foo.bar(t2)

func = foo.bar

c = func(t1)
d = func(t2)

t2b = cast(T2b, object())

e = foo.bar(t2b)
