import os
import csv
import re
from collections import defaultdict
from datetime import datetime
import matplotlib.pyplot as plt
import pandas as pd

def simplify_to_monthly_ending_values(account_dict):
    parsed = []
    for date_str, values in account_dict.items():
        padded = date_str.zfill(8)
        try:
            dt = datetime.strptime(padded, "%m%d%Y")
            month_key = dt.strftime("%m/%y")
            parsed.append((dt, month_key, values["ending"]))
        except ValueError:
            # skip bad dates
            continue
    parsed.sort(key=lambda x: x[0])
    return {month: ending for _, month, ending in parsed}

def extract_statements_data():
    data = defaultdict(dict)
    for fn in os.listdir('.'):
        if fn.startswith("Statement") and fn.endswith(".csv"):
            m = re.search(r'Statement(\d+)', fn)
            if not m:
                continue
            date_str = m.group(1)
            with open(fn, newline='', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f, restval="")
                for row in reader:
                    acct = row.get("Account Type", "").strip()
                    if not acct or "ROTH" not in acct:
                        continue
                    b = row.get("Beginning mkt Value", "").replace(",", "").strip()
                    e = row.get("Ending mkt Value",   "").replace(",", "").strip()
                    try:
                        b, e = float(b), float(e)
                    except ValueError:
                        continue
                    data[acct][date_str] = {"beginning": b, "ending": e}
    return data

# --- Main flow ---
print("Extracting data from CSV files...\n")
account_data = extract_statements_data()

# 1) Print & plot each portfolio
for acct, monthly in account_data.items():
    monthly_end = simplify_to_monthly_ending_values(monthly)
    print(f"\n{acct}:")
    print(monthly_end)

    months = list(monthly_end.keys())
    vals   = list(monthly_end.values())

    plt.figure(figsize=(8,4))
    plt.plot(months, vals, marker='o')
    plt.title(f"{acct} — Ending Market Value")
    plt.xlabel("Month")
    plt.ylabel("Value ($)")
    plt.xticks(rotation=45)
    plt.grid(True)
    plt.tight_layout()
    plt.show()

# 2 Build combined CSV for all portfolios
combined = defaultdict(dict)
for acct, monthly in account_data.items():
    monthly_end = simplify_to_monthly_ending_values(monthly)
    for m, val in monthly_end.items():
        combined[m][acct] = val

df = pd.DataFrame.from_dict(combined, orient="index")
df.index.name = "Month"
df["__dt"] = pd.to_datetime(df.index, format="%m/%y")
df = df.sort_values("__dt").drop(columns="__dt")
df.to_csv("portfolio_summary.csv")

print("\nSaved chronologically sorted data to portfolio_summary.csv")
