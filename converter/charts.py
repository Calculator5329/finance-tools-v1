import pandas as pd
import matplotlib.pyplot as plt

# Load your combined CSV
df = pd.read_csv("all_data.csv", index_col="Month")

# 1) Compute total per account and sort descending
col_order = df.sum(axis=0).sort_values(ascending=False).index.tolist()

# 2) Plot stacked bars in that order
fig, ax = plt.subplots(figsize=(12,6))
months = df.index.tolist()
bottom = [0] * len(df)

for col in col_order:
    ax.bar(months, df[col], bottom=bottom, label=col)
    bottom = [b + v for b, v in zip(bottom, df[col])]

ax.set_title("Overall Net Worth Over Time by Account")
ax.set_xlabel("Month")
ax.set_ylabel("Value ($)")
plt.xticks(rotation=45)
ax.legend(loc='upper left', bbox_to_anchor=(1,1))
plt.tight_layout()
plt.show()
