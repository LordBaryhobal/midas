# type: ignore
# ruff: disable [F821]

distance = cast(Meter, 123.45)
time = cast(Second, 6.7)
speed = distance / time
print(speed)
