from __future__ import annotations

import numpy as np
import pandas as pd


def profile_dataframe(df: pd.DataFrame) -> dict:
    missing_pct = (df.isna().mean() * 100).round(2).to_dict()
    unique_counts = df.nunique(dropna=True).to_dict()
    dtypes = {k: str(v) for k, v in df.dtypes.to_dict().items()}

    numeric_cols = df.select_dtypes(include=np.number).columns.tolist()
    stats = {}
    if numeric_cols:
        describe = df[numeric_cols].describe().replace([np.inf, -np.inf], np.nan).fillna(0)
        stats = {
            col: {metric: float(value) for metric, value in describe[col].to_dict().items()}
            for col in describe.columns
        }

    return {
        "row_count": int(len(df)),
        "column_count": int(len(df.columns)),
        "column_types": dtypes,
        "missing_percentage": missing_pct,
        "unique_counts": unique_counts,
        "basic_statistics": stats,
    }
