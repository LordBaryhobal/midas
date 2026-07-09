a: int = 3
b: int = 4

c = a + b  # -> int

c = "invalid"  # -> can't assign str to int variable

d = True
e = d + d  # -> addition not defined between booleans

f: float = a

f = -f
