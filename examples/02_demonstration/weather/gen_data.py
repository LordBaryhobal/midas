import datetime
import random

import pandas as pd

stations = ["SIO", "AIG", "ZER"]

start_ts = datetime.datetime(2026, 1, 1)
end_ts = datetime.datetime(2027, 1, 1)
delta = end_ts - start_ts

min_temp, max_temp = -30.0, 100.0
min_pres, max_pres = 800.0, 1100.0
min_hum, max_hum = 0.0, 1.0

N = 3000

rows: list[tuple[str, datetime.datetime, float, float, float]] = []

for _ in range(N):
    ts = random.random() * delta + start_ts
    rows.append(
        (
            random.choice(stations),
            ts,
            random.random() * (max_temp - min_temp) + min_temp,
            random.random() * (max_pres - min_pres) + min_pres,
            random.random() * (max_hum - min_hum) + min_hum,
        )
    )

df = pd.DataFrame(
    rows,
    columns=[
        "station_id",
        "timestamp",
        "temperature",
        "pressure",
        "humidity",
    ],
)
df = df.sort_values(by=["timestamp", "station_id"])
df.to_csv("data.csv", index=False)
