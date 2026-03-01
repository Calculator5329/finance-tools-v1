# Finance Tools

A comprehensive suite of financial analysis and visualization tools featuring bank transaction categorization, portfolio tracking, and interactive charts.

## What It Is

A full-stack financial management platform that processes bank transactions, categorizes them using AI, and provides visual analytics of spending and portfolio performance. It includes a Python backend for data processing and AI analysis, and a Next.js frontend for interactive visualization and portfolio tracking.

## Tech Stack

### Backend
- **Python**: Core data processing and AI integration
- **Google AI (Gemini)**: Transaction categorization with natural language
- **Data Processing**: pandas, CSV handling
- **Visualization**: matplotlib

### Frontend
- **Framework**: Next.js 15 with Turbopack
- **Charts**: Recharts, D3.js, Plotly
- **Data**: PapaParse for CSV handling
- **Styling**: Tailwind CSS
- **UI**: React 19

## Getting Started

### Backend Setup

```bash
cd converter
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
# Install dependencies as needed
```

To process bank statements:

```bash
python main.py        # Extract and combine portfolio data
python ai-convert.py  # Categorize transactions using AI
python pkl_convert.py # Convert data to different formats
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

The frontend will be available at `http://localhost:3000`

### Building Frontend for Production

```bash
npm run build
npm start
```

## Core Features

- **Transaction Categorization**: AI-powered categorization of bank transactions using Google Gemini
- **Portfolio Tracking**: Monitor multiple investment accounts over time
- **Visual Analytics**: Charts and graphs for spending and portfolio trends
- **CSV Processing**: Import and merge bank statement data
- **Data Export**: Convert between CSV, JSON, and other formats

## Project Structure

```
finance/
├── converter/           # Main Python backend
│   ├── main.py         # Portfolio data extraction
│   ├── ai-convert.py   # AI transaction categorization
│   ├── pkl_convert.py  # Format conversion
│   └── data/           # Input/output data files
├── chart_convert/      # Chart generation utilities
├── frontend/           # Next.js visualization app
│   ├── src/
│   ├── public/
│   └── package.json
└── .gitignore
```

## Data Files

The converter processes various CSV files:
- `Statement[date].csv` - Bank statements
- `AccountHistory.csv` - Account transaction history
- `portfolios.csv` - Portfolio definitions
- `roth.csv` - Roth IRA data
- `sp500_cumulative.csv` - S&P 500 benchmark data

## Development Notes

- Requires Google AI API key for transaction categorization
- Backend processes CSV files from banks and brokerage statements
- Frontend pulls processed data from backend for visualization
- Data is stored in JSON format for easy consumption by frontend
