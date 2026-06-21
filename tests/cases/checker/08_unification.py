def double(value: float) -> float:
    return value * 2


def is_odd(value: int) -> bool:
    return bool(value % 2)


floats: list[float] = [0.2, 0.5, 0.1, 1.2]
ints: list[int] = [1, 2, 6, -3]

doubled_floats = map(double, floats)
doubled_ints = map(double, ints)
odd_ints = map(is_odd, ints)
