# type: ignore
# ruff: disable [F821]
p1: Coordinate
p2: Coordinate

diff_x = p2.x - p1.x
diff_y = p2.y - p1.y

dist = diff_x + diff_y

p2.x += cast(Meter, 1)
