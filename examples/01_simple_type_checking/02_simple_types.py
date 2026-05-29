# type: ignore
# ruff: disable [F821]

midas.using("02_simple_types.midas")

distance: Meter = cast(Meter, 123.45)
time: Second = cast(Second, 6.7)
speed = distance / time
