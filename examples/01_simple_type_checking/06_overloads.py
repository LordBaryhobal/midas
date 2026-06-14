# type: ignore
# ruff: disable [F821]

foo: Foo
t1: T1
t2: T2

a = foo.bar(t1)
b = foo.bar(t2)

func = foo.bar

c = func(t1)
d = func(t2)
