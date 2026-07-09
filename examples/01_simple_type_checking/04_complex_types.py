# type: ignore
# ruff: disable [F821]

p1 = cast(Coordinate, object())
p2 = cast(Coordinate, object())

diff_x = p2.x - p1.x
diff_y = p2.y - p1.y

dist = diff_x + diff_y

p2.x += cast(Meter, 1.0)
p2.y = True  # invalid, wrong type
p2.z = 3  # invalid, no property 'z' on Coordinate
p2.x.a = 3  # invalid, no properties on Meter

foo = cast(list[float], [])

append = foo.append

foo.append("")  # invalid, must be float
foo.append(2)
append(True)  # invalid, must be float
append(2)

bar = cast(list[list[Meter]], [])

bar.append([p2.x])

foo2 = foo + foo

a = foo[0]
b = bar[0][1]
c = bar[0][1][2]  # invalid, not method __getitem__ on Meter
c = bar[""]  # invalid, wrong index type

d = foo[1:2]
