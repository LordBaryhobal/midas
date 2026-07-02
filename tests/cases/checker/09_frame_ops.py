# type: ignore
# ruff: disable [F821]

df1: Frame[a:int, b:float]
df2: Frame[a:int, b:float]

_: Any
_ = df1 + df2
_ = df1 - df2
_ = df1 * df2
_ = df1 / df2
_ = df1 // df2
_ = df1 % df2
_ = df1**df2

_ = df1 < df2
_ = df1 > df2
_ = df1 <= df2
_ = df1 >= df2
_ = df1 != df2
_ = df1 == df2
