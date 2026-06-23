from typing import Optional

from midas.checker.types import ColumnType, DataFrameType


class FrameManager:
    @classmethod
    def set_column(
        cls, frame: DataFrameType, name: str, column: ColumnType
    ) -> DataFrameType:
        new_columns: list[DataFrameType.Column] = []
        index: int = len(frame.columns)
        replace: bool = False
        for i, col in enumerate(frame.columns):
            if col.name == name:
                index = i
                replace = True
            new_columns.append(col)

        new_col: DataFrameType.Column = DataFrameType.Column(
            index=index,
            name=name,
            type=column,
        )
        if replace:
            new_columns[index] = new_col
        else:
            new_columns.append(new_col)

        return DataFrameType(columns=new_columns)

    @classmethod
    def set_columns(
        cls, frame: DataFrameType, names: list[str], columns: list[ColumnType]
    ) -> DataFrameType:
        for name, col in zip(names, columns):
            frame = cls.set_column(frame, name, col)
        return frame

    @classmethod
    def get_column(cls, frame: DataFrameType, name: str) -> Optional[ColumnType]:
        for col in frame.columns:
            if col.name == name:
                return col.type
        return None

    @classmethod
    def get_columns(
        cls, frame: DataFrameType, names: list[str]
    ) -> list[Optional[ColumnType]]:
        return [cls.get_column(frame, name) for name in names]
