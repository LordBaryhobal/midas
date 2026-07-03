# type: ignore
# ruff: disable [F821]

df1: Frame[a:int, b:float]
df2: Frame[a:int, b:float]

_: Any

# Arithmetic
_ = df1 + df2
_ = df1 - df2
_ = df1 * df2
_ = df1 / df2
_ = df1 // df2
_ = df1 % df2
_ = df1**df2

# Comparisons
_ = df1 < df2
_ = df1 > df2
_ = df1 <= df2
_ = df1 >= df2
_ = df1 != df2
_ = df1 == df2

# Aggregate
_ = df1.kurt()
_ = df1.kurtosis()
_ = df1.max()
_ = df1.mean()
_ = df1.median()
_ = df1.min()
_ = df1.mode()
_ = df1.prod()
_ = df1.product()
_ = df1.std()
_ = df1.sum()
_ = df1.var()

# Groupby
gb = df1.groupby(by="a")

_ = gb.kurt()
_ = gb.max()
_ = gb.mean()
_ = gb.median()
_ = gb.min()
_ = gb.prod()
_ = gb.std()
_ = gb.sum()
_ = gb.var()
