# type: ignore
# ruff: disable[F821]

import module1
import module2 as alias2
from module3 import submodule3
from module4 import submodule4 as alias4

a: int
b: Generic[int]
c: Generic2[int, float]
d: Frame[a:int, b:float]

e = 3
f: int = 4
g = []
h = [1, 0.1, " ", None, False, True]
i = {}
j = {"a": 1, "b": 2}
k = {"c": 3, **j}
l = cast(int, a)
m = unsafe_cast(int, a)


def n(a: int, /, b: float, *, c: str) -> Any:
    return


def o(a: int = 1, /, b: float = 2.0, *, c: str = "") -> Any:
    return 1


for i in h:
    pass

if e == f:
    pass
elif f == g:
    pass
else:
    pass

p = +a + -b - ~c * d / e**f
q = not (a and b) or c
r = a & b | c ^ d

s = a.b.c
t = a[b][c, d][e:f]
u = a(b)(c=d)
