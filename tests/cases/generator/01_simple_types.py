from midas import cast, Meter, Second

distance: Meter = cast(Meter, 123.45)
time: Second = cast(Second, 6.7)
speed = distance / time
