from typing import TypeVar

from demo_stubs import CHF, EUR, USD, Currency, Discount, Price

from midas.typing import cast, unsafe_cast

T = TypeVar("T", bound=Currency)


def apply_discount(amount: Price[T], discount: Discount) -> Price[T]:
    return cast(Price[T], (1.0 - discount) * amount)


a1 = cast(Price[EUR], 3.2)
a2 = cast(Price[USD], 10.4)
r1 = cast(Discount, 0.2)

print(apply_discount(a1, r1))
print(apply_discount(a2, r1))

a3 = a1 + a1
a4 = a1 + a2  # cannot add euros and dollars
a3 = a2  # cannot change variable type

dyn_price = float(input("Price (CHF): "))
dyn_discount = float(input("Discount (0.0-1.0): "))
discounted = apply_discount(
    cast(Price[CHF], dyn_price),
    cast(Discount, dyn_discount),
)

print(f"Discounted: CHF {discounted}")

large_data = [i * 10 for i in range(100)]
prices = unsafe_cast(list[Price[EUR]], large_data)
