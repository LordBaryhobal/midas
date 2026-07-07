from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from custom_types import DailyAverages, Data, DataWithHI, HeatIndex, RawData

from midas.typing import Column, cast, unsafe_cast


def load_data(path: Path) -> RawData:
    # Check base types and dataframe structure
    return cast(RawData, pd.read_csv(path))


def convert_data(raw_df: RawData) -> Data:
    new_df = raw_df.copy()
    new_df["timestamp"] = cast(
        Column[object],
        pd.to_datetime(new_df["timestamp"]),
    )

    # Check types and constraints at runtime, catches out-of-range values and
    # invalid types / malformed data
    return cast(Data, new_df)


def compute_heat_index(df: Data):
    # The computation's result can only be typed as `Column[float]`
    # Casting is necessary to bring back semantic
    df["heat_index"] = cast(
        Column[HeatIndex],
        (
            df["temperature"] * 2.0
            + df["humidity"] * 10.0
            - df["temperature"] * df["humidity"] * 0.2
        ),
    )
    return df


def daily_avg(df: DataWithHI):
    # Group-by and aggregation methods keep the structure of the dataframe but
    # may erase the exact types
    # The type checker is still very conservative and often the result of most
    # aggregation methods as `Column[Any]`
    return cast(
        DailyAverages,
        df.groupby(
            by=[
                df["station_id"],
                df["timestamp"].dt.day.rename("day"),
            ],
        )
        .mean()
        .sort_values(by="timestamp"),
    )


def plot(df: DailyAverages):
    # Some operations are not implemented in Midas but the user can still use
    # them, they will just not be fully type-checked
    # `unsafe_cast` can also be used to avoid trivial, redundant or costly checks
    stations = unsafe_cast(list[str], list(df.index.get_level_values(0).unique()))
    for station in stations:
        sub_df = unsafe_cast(DailyAverages, df.loc[station])
        plt.plot(sub_df["timestamp"], sub_df["heat_index"])
    plt.show()


def main():
    # Assigning to annotated variables help catch errors
    raw_df: RawData = load_data(Path("data.csv"))
    df: Data = convert_data(raw_df)

    with_hi = compute_heat_index(df)
    dailies = daily_avg(with_hi)
    plot(dailies)


if __name__ == "__main__":
    main()
