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
df_gb = df1.groupby(by="a")

_ = df_gb.kurt()
_ = df_gb.max()
_ = df_gb.mean()
_ = df_gb.median()
_ = df_gb.min()
_ = df_gb.prod()
_ = df_gb.std()
_ = df_gb.sum()
_ = df_gb.var()


# Columns

col1 = df1["a"]
col2 = df1["a"]

# Arithmetic
_ = col1 + col2
_ = col1 - col2
_ = col1 * col2
_ = col1 / col2
_ = col1 // col2
_ = col1 % col2
_ = col1**col2

# Comparisons
_ = col1 < col2
_ = col1 > col2
_ = col1 <= col2
_ = col1 >= col2
_ = col1 != col2
_ = col1 == col2

# Aggregate
_ = col1.kurt()
_ = col1.kurtosis()
_ = col1.max()
_ = col1.mean()
_ = col1.median()
_ = col1.min()
_ = col1.mode()
_ = col1.prod()
_ = col1.product()
_ = col1.std()
_ = col1.sum()
_ = col1.var()

# Groupby
col_gb = col1.groupby(level=0)

_ = col_gb.kurt()
_ = col_gb.max()
_ = col_gb.mean()
_ = col_gb.median()
_ = col_gb.min()
_ = col_gb.prod()
_ = col_gb.std()
_ = col_gb.sum()
_ = col_gb.var()

# Attributes
_ = df1.ndim  # int
_ = df1.size  # int
_ = df1.shape  # (int, int)
_ = col1.ndim  # int
_ = col1.size  # int
_ = col1.shape  # (int)
_ = col1.T  # Column[int]


# Misc
_ = df1.head()
_ = df1.tail()
_ = col1.head()
_ = col1.tail()
