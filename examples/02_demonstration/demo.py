from typing import TypeVar, cast

from demo_stubs import EUR, USD, Money, Price, Reduction

T = TypeVar("T", bound=Money)


def apply_reduction(amount: Price[T], reduction: Reduction) -> Price[T]:
    return cast(Price[T], (1.0 - reduction) * amount)


a1 = cast(Price[EUR], 3.2)
a2 = cast(Price[USD], 10.4)
r1: Reduction = cast(Reduction, 0.2)

print(apply_reduction(a1, r1))
print(apply_reduction(a2, r1))

# a3 = a1 + a2
