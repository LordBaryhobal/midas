# type: ignore
# ruff: disable [F821]

p1: Coordinate
p2: Coordinate

diff_x = p2.x - p1.x
diff_y = p2.y - p1.y

dist = diff_x + diff_y

p2.x += cast(Meter, 1)
p2.y = True  # invalid, wrong type
p2.z = 3  # invalid, no property 'z' on Coordinate
p2.x.a = 3  # invalid, no properties on Meter

foo: list[float] = []

append = foo.append

foo.append("")  # invalid, must be float
foo.append(2)
append(True)  # invalid, must be float
append(2)

bar: list[list[Meter]]

bar.append([p2.x])

foo2 = foo + foo
