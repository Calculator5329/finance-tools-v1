#!/usr/bin/env python3
import pandas as pd
from datetime import datetime
import matplotlib.pyplot as plt

def load_csv_to_df(path):
    df = pd.read_csv(path)
    if "Month" not in df.columns:
        raise RuntimeError(f"{path} must have a 'Month' column")
    df = df.set_index("Month")
    return df

def main():
    # 1) Load your two files
    portfolios = load_csv_to_df("portfolios.csv")
    roth       = load_csv_to_df("roth.csv")

    # 2) Outer‐join them on Month
    df = portfolios.join(roth, how="outer")

    # 3) Add Tesla data
    tesla_data = {
        "04/24": 1898.25, "05/24": 2149.34, "06/24": 2403.52, "07/24": 2660.81,
        "08/24": 2921.20, "09/24": 3184.72, "10/24": 3451.36, "11/24": 3721.14,
        "12/24": 3994.06, "01/25": 4270.14, "02/25": 4549.37, "03/25": 4831.79,
        "04/25": 5117.38, "05/25": 5406.16
    }
    df = df.join(pd.Series(tesla_data, name="Tesla"), how="outer")

    # 4) Fill all gaps with zero
    df = df.fillna(0)

    # 5) Sort by real date
    df["__dt"] = pd.to_datetime(df.index, format="%m/%y")
    df = df.sort_values("__dt").drop(columns="__dt")

    # 6) Save combined CSV
    df.to_csv("all_data.csv")
    print("✔  all_data.csv written.")

    # 7) Plot each column
    for col in df.columns:
        plt.figure(figsize=(8,4))
        plt.plot(df.index, df[col], marker="o")
        plt.title(f"{col} Over Time")
        plt.xlabel("Month")
        plt.ylabel("Value")
        plt.xticks(rotation=45)
        plt.grid(True)
        plt.tight_layout()
        plt.show()

if __name__ == "__main__":
    main()
