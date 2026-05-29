# type: ignore
# ruff: disable [F821]

midas.using("04_custom_types.midas")

distance: Meter = 123.45
time: Second = 6.7
speed = distance / time
