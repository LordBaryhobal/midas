# type: ignore
# ruff: disable[F821]

_: Any

_ = undeclared

declared: int
_ = declared

half_defined1: int
half_defined2: int
if False:
    half_defined1 = 0
else:
    half_defined2 = 1
_ = half_defined1
_ = half_defined2

fully_defined: int
if False:
    fully_defined = 0
else:
    fully_defined = 1
_ = fully_defined

defined: int = 0
_ = defined

no_annotation = 0
_ = no_annotation

self_ref1 = self_ref1
self_ref2: int = self_ref2


def fact(n: int) -> int:
    if n <= 1:
        return 1
    return n * fact(n - 1)


for i in [1, 2, 3]:
    _ = i
_ = i
