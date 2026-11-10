# Stock Fetcher

A modular, multi-provider Python financial analysis and stock reporting CLI. Fetches real-time equity quotes, valuation ratios, profitability margins, earnings dates, multi-year cash flow statements, and historical performance metrics. Supports clean terminal output and styled Excel (`.xlsx`) exports.

---

## Features

- **Multi-Provider Architecture**:
  - **Yahoo Finance (`--provider yahoo`)**: Complete market metrics, financial statement data, annual cash flow statements, and multi-decade performance returns.
  - **Robinhood (`--provider robinhood`)**: Integration using `robin-stocks`, supporting automated TOTP MFA via `pyotp` or interactive terminal challenge handling.
- **Comprehensive Financial Metrics**:
  - **Quotes & Valuation**: Current Price, Change, %, Trailing & Forward P/E, Market Cap, Dividend Yield, and Upcoming Earnings Dates.
  - **Profitability & Margins**: Gross Margin, Operating Margin, Net Profit Margin, EBITDA Margin, Return on Assets (ROA), and Return on Equity (ROE).
  - **Income & Financials**: Revenue, Gross Profit, Operating Income, Net Income, and Trailing EPS.
  - **Cash Flow Statement**: Annual fiscal breakdown of Operating Cash Flow, Capital Expenditures (CapEx), Free Cash Flow (FCF), Investing Cash Flow, Financing Cash Flow, and End Cash Position.
  - **Performance Returns**: Trailing return percentages for YTD, 1-Year, 5-Year, and 10-Year horizons.
  - **Historical OHLCV**: Recent trading days breakdown with Open, High, Low, Close, and Volume.
- **Excel Export (`--excel [FILENAME]`)**:
  - Optional flag generating professional multi-tab workbooks via `openpyxl`.
  - `Overview` tab: High-level comparative summary table across all requested symbols.
  - `<SYMBOL>_CashFlow` tabs: Full multi-year statement tables per company.
  - `<SYMBOL>_History` tabs: Timezone-sanitized historical daily price data.
- **Unit Tested**: Isolated test suite with mocked network calls and comprehensive data validation.

---

## Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/shreyamsh/agy-demo.git
   cd agy-demo
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

*(Dependencies include: `yfinance`, `pandas`, `robin-stocks`, `python-dotenv`, `pyotp`, and `openpyxl`).*

---

## Quick Start & Usage

### 1. Terminal Reports (Default: Yahoo Finance)
```bash
# Analyze a single stock (defaults to AAPL)
python3 stock_fetcher.py AAPL

# Analyze multiple stocks with custom historical days
python3 stock_fetcher.py AAPL MSFT NVDA -d 10
```

### 2. Exporting to Excel
The `--excel` (or `--export-excel`) flag is optional. If passed without arguments, it defaults to `stocks_report.xlsx`:
```bash
# Export to default 'stocks_report.xlsx'
python3 stock_fetcher.py AAPL MSFT --excel

# Export to a custom workbook filename
python3 stock_fetcher.py AAPL GOOGL AMZN --excel tech_portfolio.xlsx
```

### 3. Using Robinhood as Provider
```bash
# Run with Robinhood backend
python3 stock_fetcher.py --provider robinhood AAPL TSLA
```

---

## Robinhood Authentication Setup

To use `--provider robinhood`, configure credentials via a local `.env` file or enter them interactively in the terminal.

1. **Create `.env` from template**:
   ```bash
   cp .env.example .env
   ```

2. **Populate credentials**:
   ```ini
   ROBINHOOD_USERNAME=your_email@example.com
   ROBINHOOD_PASSWORD=your_password

   # Optional for automated 2FA:
   # In Robinhood app/web: Settings -> Security -> Two-Factor Authentication -> Authenticator App -> Can't scan barcode / Manual Key
   ROBINHOOD_MFA_SECRET=your_base32_totp_secret_key
   ```

> [!NOTE]
> If credentials or `ROBINHOOD_MFA_SECRET` are not set in `.env`, the script will interactively prompt in your terminal for credentials and verification codes. Both `.env` and session tokens are protected in `.gitignore`.

---

## CLI Reference

```text
usage: stock_fetcher.py [-h] [--provider {yahoo,robinhood}]
                        [--history-days HISTORY_DAYS] [--excel [FILE]]
                        [symbols ...]

Fetch and display financial stock reports.

positional arguments:
  symbols               Stock ticker symbols to fetch (e.g. AAPL MSFT GOOGL)

options:
  -h, --help            show this help message and exit
  --provider {yahoo,robinhood}, -p {yahoo,robinhood}
                        Stock data provider backend (default: yahoo)
  --history-days HISTORY_DAYS, -d HISTORY_DAYS
                        Number of historical trading days to display (default: 5)
  --excel [FILE], --export-excel [FILE]
                        Export fetched stock data to an Excel file (.xlsx) (default: stocks_report.xlsx)
```

---

## Running Tests

Run the automated test suite:
```bash
python3 -m unittest discover tests
```

---

## Project Structure

```text
agy-demo/
├── .env.example                       # Credential configuration template
├── .gitignore                         # Git exclusion rules (.env, *.pickle, *.xlsx)
├── README.md                          # Project documentation
├── requirements.txt                   # Project package dependencies
├── stock_fetcher.py                   # Core application, provider classes & CLI
└── tests/
    ├── test_robinhood_provider.py     # Unit tests for Robinhood provider & TOTP
    └── test_excel_and_fundamentals.py # Unit tests for Excel export & fundamentals
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.
