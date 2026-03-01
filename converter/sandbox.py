import pandas as pd

# Define the monthly returns
returns = {
    'Jan 2023': 6.18,
    'Feb 2023': -2.61,
    'Mar 2023': 3.10,
    'Apr 2023': -4.08,
    'May 2023': 4.80,
    'Jun 2023': 3.47,
    'Jul 2023': 1.13,
    'Aug 2023': 2.28,
    'Sep 2023': 2.02,
    'Oct 2023': -0.99,
    'Nov 2023': 5.73,
    'Dec 2023': -2.50,
    'Jan 2024': 2.70,
    'Feb 2024': -1.42,
    'Mar 2024': 3.10,
    'Apr 2024': -4.16,
    'May 2024': 4.80,
    'Jun 2024': 3.47,
    'Jul 2024': 1.13,
    'Aug 2024': 2.28,
    'Sep 2024': 2.02,
    'Oct 2024': -0.99,
    'Nov 2024': 5.73,
    'Dec 2024': -2.50,
    'Jan 2025': 2.70,
    'Feb 2025': -1.42,
    'Mar 2025': -5.75,
    'Apr 2025': -1.23
}

# Initialize the DataFrame
df = pd.DataFrame(list(returns.items()), columns=['Month', 'Return'])

# Calculate cumulative value
initial_value = 100
values = [initial_value]
for r in df['Return']:
    new_value = values[-1] * (1 + r / 100)
    values.append(round(new_value, 2))

# Remove the initial value used for calculation
values = values[1:]

# Add the values to the DataFrame
df['S&P 500 Value'] = values

# Save to CSV
df.to_csv('sp500_cumulative.csv', index=False)
