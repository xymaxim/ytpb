import numpy as np
import pandas as pd


def discrete_diff(data: pd.DataFrame) -> pd.DataFrame:
    return data.shift(-1) - data


def interpolate_point(x, xp, fp) -> tuple[float, float]:
    return x, np.interp(x, xp, fp)
