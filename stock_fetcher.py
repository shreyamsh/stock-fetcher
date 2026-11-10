import os
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv
import pandas as pd
import yfinance as yf

# Load environment variables from .env if present
load_dotenv()


@dataclass
class StockQuote:
    symbol: str
    name: str = ""
    price: float = 0.0
    change: Optional[float] = None
    percent_change: Optional[float] = None
    currency: str = "USD"
    timestamp: str = ""


@dataclass
class StockFundamentals:
    """Valuation, financial statement, profitability, and cash flow metrics."""
    market_cap: Optional[float] = None
    trailing_pe: Optional[float] = None
    forward_pe: Optional[float] = None
    roa: Optional[float] = None           # Return on Assets (decimal from provider)
    roe: Optional[float] = None           # Return on Equity (decimal from provider)
    dividend_rate: Optional[float] = None # Annual dividend payment ($)
    dividend_yield: Optional[float] = None # Dividend yield (%)
    total_revenue: Optional[float] = None
    gross_profit: Optional[float] = None
    operating_income: Optional[float] = None
    net_income: Optional[float] = None
    trailing_eps: Optional[float] = None
    earnings_date: Optional[str] = None
    # Profitability Margins
    profit_margin: Optional[float] = None     # Net Profit Margin (decimal)
    operating_margin: Optional[float] = None  # Operating Margin (decimal)
    gross_margin: Optional[float] = None      # Gross Margin (decimal)
    ebitda_margin: Optional[float] = None     # EBITDA Margin (decimal)
    # Cash Flow Highlights
    free_cash_flow: Optional[float] = None
    operating_cash_flow: Optional[float] = None
    capital_expenditure: Optional[float] = None


@dataclass
class StockPerformance:
    """Performance return percentages across multiple time horizons."""
    ytd: Optional[float] = None
    one_year: Optional[float] = None
    five_year: Optional[float] = None
    ten_year: Optional[float] = None


@dataclass
class StockData:
    quote: StockQuote
    fundamentals: StockFundamentals
    performance: StockPerformance
    historical_data: pd.DataFrame
    cash_flow_statement: Optional[pd.DataFrame] = None


class StockDataProvider(ABC):
    """Abstract Base Class for stock data providers.
    
    This ensures that switching from Yahoo Finance to Robinhood (or any other API)
    requires changing only the provider implementation, not client code.
    """

    @abstractmethod
    def get_stock_data(self, symbol: str, history_days: int = 5) -> StockData:
        """Fetch quote, fundamentals, multi-period performance, and recent historical data."""
        pass

    @abstractmethod
    def get_quote(self, symbol: str) -> StockQuote:
        """Fetch latest price / quote for a given symbol."""
        pass

    @abstractmethod
    def get_historical_data(self, symbol: str, period: str = "5d", interval: str = "1d") -> pd.DataFrame:
        """Fetch historical price data as a pandas DataFrame."""
        pass


class YahooFinanceProvider(StockDataProvider):
    """Stock data provider backed by Yahoo Finance (yfinance)."""

    def get_stock_data(self, symbol: str, history_days: int = 5) -> StockData:
        ticker = yf.Ticker(symbol)
        info = ticker.info

        # 1. Quote
        fast = ticker.fast_info
        last_price = float(fast.last_price) if getattr(fast, "last_price", None) is not None else float(info.get("currentPrice") or info.get("regularMarketPrice") or 0.0)
        prev_close = float(fast.previous_close) if getattr(fast, "previous_close", None) is not None else float(info.get("previousClose") or last_price)
        change = round(last_price - prev_close, 2)
        pct_change = round((change / prev_close) * 100, 2) if prev_close else 0.0
        company_name = info.get("shortName") or info.get("longName") or symbol.upper()

        quote = StockQuote(
            symbol=symbol.upper(),
            name=company_name,
            price=round(last_price, 2),
            change=change,
            percent_change=pct_change,
            currency=getattr(fast, "currency", "USD") or info.get("currency", "USD") or "USD",
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

        # 2. Operating Income (check income_stmt, fallback to totalRevenue * operatingMargins)
        operating_income = None
        try:
            stmt = ticker.income_stmt
            if stmt is not None and not stmt.empty and "Operating Income" in stmt.index:
                operating_income = float(stmt.loc["Operating Income"].iloc[0])
        except Exception:
            pass

        if operating_income is None:
            rev = info.get("totalRevenue")
            margin = info.get("operatingMargins")
            if rev is not None and margin is not None:
                operating_income = float(rev) * float(margin)

        # 3. Earnings Date
        earnings_date = None
        try:
            cal = getattr(ticker, "calendar", None)
            if isinstance(cal, dict) and "Earnings Date" in cal:
                val = cal["Earnings Date"]
                if isinstance(val, (list, tuple)) and len(val) > 0:
                    earnings_date = str(val[0])
                elif val:
                    earnings_date = str(val)
            elif hasattr(cal, "get") and cal.get("Earnings Date") is not None:
                earnings_date = str(cal.get("Earnings Date"))
        except Exception:
            pass

        if not earnings_date and info.get("earningsTimestamp"):
            try:
                earnings_date = datetime.fromtimestamp(info["earningsTimestamp"]).strftime("%Y-%m-%d")
            except Exception:
                pass

        # 4. Cash Flow Statement & Cash Flow Metrics
        cash_flow_stmt = None
        operating_cf = None
        capex = None
        free_cf = None
        try:
            cf = ticker.cashflow
            if cf is not None and not cf.empty:
                cash_flow_stmt = cf.copy()
                cash_flow_stmt.columns = [
                    c.strftime("%Y-%m-%d") if hasattr(c, "strftime") else str(c)[:10]
                    for c in cash_flow_stmt.columns
                ]
                cash_flow_stmt.index.name = "Line Item"
                if "Operating Cash Flow" in cf.index:
                    operating_cf = float(cf.loc["Operating Cash Flow"].iloc[0])
                if "Capital Expenditure" in cf.index:
                    capex = float(cf.loc["Capital Expenditure"].iloc[0])
                if "Free Cash Flow" in cf.index:
                    free_cf = float(cf.loc["Free Cash Flow"].iloc[0])
        except Exception:
            pass

        if free_cf is None and info.get("freeCashflow") is not None:
            free_cf = float(info["freeCashflow"])
        if operating_cf is None and info.get("operatingCashflow") is not None:
            operating_cf = float(info["operatingCashflow"])

        # 5. Fundamentals & Profitability
        fundamentals = StockFundamentals(
            market_cap=info.get("marketCap"),
            trailing_pe=info.get("trailingPE"),
            forward_pe=info.get("forwardPE"),
            roa=info.get("returnOnAssets"),
            roe=info.get("returnOnEquity"),
            dividend_rate=info.get("dividendRate"),
            dividend_yield=info.get("dividendYield"),
            total_revenue=info.get("totalRevenue"),
            gross_profit=info.get("grossProfits"),
            operating_income=operating_income,
            net_income=info.get("netIncomeToCommon"),
            trailing_eps=info.get("trailingEps"),
            earnings_date=earnings_date,
            profit_margin=info.get("profitMargins"),
            operating_margin=info.get("operatingMargins"),
            gross_margin=info.get("grossMargins"),
            ebitda_margin=info.get("ebitdaMargins"),
            free_cash_flow=free_cf,
            operating_cash_flow=operating_cf,
            capital_expenditure=capex,
        )

        # 6. Long history (covers up to 10+ years) for performance returns and recent history
        long_hist = ticker.history(period="11y")
        performance = self._calculate_performance(long_hist)
        recent_history = long_hist.tail(history_days)

        return StockData(
            quote=quote,
            fundamentals=fundamentals,
            performance=performance,
            historical_data=recent_history,
            cash_flow_statement=cash_flow_stmt,
        )

    def get_quote(self, symbol: str) -> StockQuote:
        ticker = yf.Ticker(symbol)
        fast = ticker.fast_info
        last_price = float(fast.last_price) if getattr(fast, "last_price", None) is not None else 0.0
        prev_close = float(fast.previous_close) if getattr(fast, "previous_close", None) is not None else last_price
        change = round(last_price - prev_close, 2)
        pct_change = round((change / prev_close) * 100, 2) if prev_close else 0.0

        return StockQuote(
            symbol=symbol.upper(),
            price=round(last_price, 2),
            change=change,
            percent_change=pct_change,
            currency=getattr(fast, "currency", "USD") or "USD",
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

    def get_historical_data(self, symbol: str, period: str = "5d", interval: str = "1d") -> pd.DataFrame:
        ticker = yf.Ticker(symbol)
        return ticker.history(period=period, interval=interval)

    @staticmethod
    def _calculate_performance(hist: pd.DataFrame) -> StockPerformance:
        if hist is None or hist.empty:
            return StockPerformance()

        current_date = hist.index[-1]
        current_close = float(hist["Close"].iloc[-1])

        # Return to date (YTD)
        ytd = None
        ytd_df = hist[hist.index.year == current_date.year]
        if not ytd_df.empty:
            start_price = float(ytd_df["Close"].iloc[0])
            if start_price:
                ytd = round(((current_close - start_price) / start_price) * 100, 2)

        # 1-Year, 5-Year, 10-Year
        period_returns = {}
        for key, years in [("1y", 1), ("5y", 5), ("10y", 10)]:
            cutoff = current_date - pd.DateOffset(years=years)
            past_df = hist[hist.index <= cutoff]
            if not past_df.empty:
                past_price = float(past_df["Close"].iloc[-1])
                if past_price:
                    period_returns[key] = round(((current_close - past_price) / past_price) * 100, 2)
                else:
                    period_returns[key] = None
            else:
                period_returns[key] = None

        return StockPerformance(
            ytd=ytd,
            one_year=period_returns.get("1y"),
            five_year=period_returns.get("5y"),
            ten_year=period_returns.get("10y"),
        )


class RobinhoodProvider(StockDataProvider):
    """Stock data provider backed by Robinhood API (via robin_stocks)."""

    def __init__(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        mfa_secret: Optional[str] = None,
    ):
        self.username = username or os.getenv("ROBINHOOD_USERNAME")
        self.password = password or os.getenv("ROBINHOOD_PASSWORD")
        self.mfa_secret = mfa_secret or os.getenv("ROBINHOOD_MFA_SECRET")
        self._authenticated = False

    def authenticate(self):
        """Authenticate with Robinhood.
        
        Uses credentials from .env, environment variables, or constructor.
        If ROBINHOOD_MFA_SECRET is set, generates TOTP dynamically.
        If credentials are not set, robin_stocks will interactively prompt in terminal.
        """
        if self._authenticated:
            return

        import robin_stocks.robinhood as r

        mfa_code = None
        if self.mfa_secret:
            try:
                import pyotp
                mfa_code = pyotp.TOTP(self.mfa_secret.strip()).now()
            except Exception as e:
                print(f"[WARNING] Failed to generate TOTP code from MFA secret: {e}", file=sys.stderr)

        try:
            r.login(
                username=self.username,
                password=self.password,
                mfa_code=mfa_code,
                expiresIn=86400,
                store_session=True,
            )
            self._authenticated = True
        except Exception as e:
            raise RuntimeError(f"Robinhood login failed: {e}") from e

    def get_quote(self, symbol: str) -> StockQuote:
        self.authenticate()
        import robin_stocks.robinhood as r

        quotes = r.stocks.get_stock_quote_by_symbol(symbol)
        if not quotes or not isinstance(quotes, dict):
            raise ValueError(f"Could not retrieve quote for symbol '{symbol}' from Robinhood.")

        last_price_raw = quotes.get("last_trade_price")
        prev_close_raw = quotes.get("previous_close")
        if last_price_raw is None:
            raise ValueError(f"No price data available for symbol '{symbol}'.")

        price = round(float(last_price_raw), 2)
        prev_close = round(float(prev_close_raw), 2) if prev_close_raw is not None else price
        change = round(price - prev_close, 2)
        pct_change = round((change / prev_close) * 100, 2) if prev_close else 0.0

        company_name = r.stocks.get_name_by_symbol(symbol) or symbol.upper()
        timestamp = quotes.get("updated_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        return StockQuote(
            symbol=symbol.upper(),
            name=company_name,
            price=price,
            change=change,
            percent_change=pct_change,
            currency="USD",
            timestamp=timestamp,
        )

    def get_historical_data(self, symbol: str, period: str = "5d", interval: str = "1d") -> pd.DataFrame:
        self.authenticate()
        import robin_stocks.robinhood as r

        span_map = {
            "1d": ("5minute", "day"),
            "5d": ("day", "week"),
            "1mo": ("day", "month"),
            "3mo": ("day", "3month"),
            "1y": ("day", "year"),
            "5y": ("day", "5year"),
            "10y": ("day", "5year"),
            "11y": ("day", "5year"),
            "max": ("day", "5year"),
        }
        rh_interval, rh_span = span_map.get(period.lower(), ("day", "5year"))

        raw_data = r.stocks.get_stock_historicals(symbol, interval=rh_interval, span=rh_span, bounds="regular")
        if not raw_data or raw_data == [None]:
            return pd.DataFrame()

        df = pd.DataFrame(raw_data)
        if df.empty or "begins_at" not in df.columns:
            return pd.DataFrame()

        df = df.rename(columns={
            "begins_at": "Date",
            "open_price": "Open",
            "high_price": "High",
            "low_price": "Low",
            "close_price": "Close",
            "volume": "Volume",
        })
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.set_index("Date")
        for col in ["Open", "High", "Low", "Close"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        if "Volume" in df.columns:
            df["Volume"] = pd.to_numeric(df["Volume"], errors="coerce").fillna(0).astype(int)

        cols = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]
        return df[cols]

    def get_stock_data(self, symbol: str, history_days: int = 5) -> StockData:
        self.authenticate()
        import robin_stocks.robinhood as r

        # 1. Quote
        quote = self.get_quote(symbol)

        # 2. Fundamentals
        fund_list = r.stocks.get_fundamentals(symbol)
        fund_dict = fund_list[0] if (fund_list and isinstance(fund_list, list) and fund_list[0]) else {}

        def to_float(val):
            try:
                return float(val) if val is not None else None
            except (ValueError, TypeError):
                return None

        # Earnings Date from Robinhood
        earnings_date = None
        try:
            earnings_info = r.stocks.get_earnings(symbol)
            if earnings_info and isinstance(earnings_info, list):
                dates = [
                    item["report"].get("date")
                    for item in earnings_info
                    if isinstance(item, dict) and isinstance(item.get("report"), dict) and item["report"].get("date")
                ]
                if dates:
                    earnings_date = dates[-1]
        except Exception:
            pass

        fundamentals = StockFundamentals(
            market_cap=to_float(fund_dict.get("market_cap")),
            trailing_pe=to_float(fund_dict.get("pe_ratio")),
            forward_pe=None,
            roa=None,
            roe=None,
            dividend_rate=None,
            dividend_yield=to_float(fund_dict.get("dividend_yield")),
            total_revenue=None,
            gross_profit=None,
            operating_income=None,
            net_income=None,
            trailing_eps=None,
            earnings_date=earnings_date,
            profit_margin=None,
            operating_margin=None,
            gross_margin=None,
            ebitda_margin=None,
            free_cash_flow=None,
            operating_cash_flow=None,
            capital_expenditure=None,
        )

        # 3. Performance and historical data
        long_hist = self.get_historical_data(symbol, period="5y", interval="1d")
        performance = YahooFinanceProvider._calculate_performance(long_hist)
        recent_history = long_hist.tail(history_days)

        return StockData(
            quote=quote,
            fundamentals=fundamentals,
            performance=performance,
            historical_data=recent_history,
            cash_flow_statement=None,
        )


def get_stock_provider(provider_name: str = "yahoo", **kwargs) -> StockDataProvider:
    """Factory function to instantiate the requested stock data provider."""
    providers = {
        "yahoo": YahooFinanceProvider,
        "robinhood": RobinhoodProvider,
    }

    provider_cls = providers.get(provider_name.lower())
    if not provider_cls:
        raise ValueError(f"Unknown provider '{provider_name}'. Supported: {list(providers.keys())}")

    return provider_cls(**kwargs)


# ---------------------------------------------------------------------------
# Display Formatting Helpers
# ---------------------------------------------------------------------------

def format_currency(val: Optional[float], currency: str = "$") -> str:
    if val is None:
        return "N/A"
    abs_val = abs(val)
    sign = "-" if val < 0 else ""
    if abs_val >= 1e12:
        return f"{sign}{currency}{abs_val / 1e12:.2f}T"
    elif abs_val >= 1e9:
        return f"{sign}{currency}{abs_val / 1e9:.2f}B"
    elif abs_val >= 1e6:
        return f"{sign}{currency}{abs_val / 1e6:.2f}M"
    elif abs_val >= 1e3:
        return f"{sign}{currency}{abs_val / 1e3:.2f}K"
    else:
        return f"{sign}{currency}{abs_val:.2f}"


def format_pct(val: Optional[float], include_plus: bool = True) -> str:
    if val is None:
        return "N/A"
    sign = "+" if (val > 0 and include_plus) else ""
    return f"{sign}{val:.2f}%"


def format_ratio(val: Optional[float]) -> str:
    if val is None:
        return "N/A"
    return f"{val:.2f}"


def print_stock_report(data: StockData):
    """Print a clean, structured financial report for a single stock."""
    q = data.quote
    f = data.fundamentals
    p = data.performance
    h = data.historical_data
    cf = data.cash_flow_statement

    sign = "+" if (q.change or 0) >= 0 else ""
    title = f"{q.symbol} - {q.name}" if q.name else q.symbol

    print("\n" + "=" * 76)
    print(f" {title.upper()}")
    print("=" * 76)
    print(f"Price: {q.price:.2f} {q.currency} | Change: {sign}{q.change:.2f} ({sign}{q.percent_change:.2f}%) | Time: {q.timestamp}")

    print("\n--- Valuation & Key Ratios ---")
    pe_str = f"{format_ratio(f.trailing_pe)}"
    if f.forward_pe:
        pe_str += f" (Forward: {format_ratio(f.forward_pe)})"
    print(f"  Earnings Date:    {f.earnings_date or 'N/A'}")
    print(f"  Market Cap:       {format_currency(f.market_cap)}")
    print(f"  P/E Ratio:        {pe_str}")
    div_str = "None"
    if f.dividend_rate or (f.dividend_yield and f.dividend_yield > 0):
        rate = f"${f.dividend_rate:.2f}/yr" if f.dividend_rate is not None else "N/A"
        yld = f"{f.dividend_yield:.2f}%" if f.dividend_yield is not None else "N/A"
        div_str = f"{rate} (Yield: {yld})"
    print(f"  Dividends:        {div_str}")

    print("\n--- Profitability & Margins ---")
    print(f"  Gross Margin:     {format_pct(f.gross_margin * 100 if f.gross_margin is not None else None, include_plus=False)}")
    print(f"  Operating Margin: {format_pct(f.operating_margin * 100 if f.operating_margin is not None else None, include_plus=False)}")
    print(f"  Net Profit Margin:{format_pct(f.profit_margin * 100 if f.profit_margin is not None else None, include_plus=False)}")
    print(f"  EBITDA Margin:    {format_pct(f.ebitda_margin * 100 if f.ebitda_margin is not None else None, include_plus=False)}")
    print(f"  Return on Assets: {format_pct(f.roa * 100 if f.roa is not None else None, include_plus=False)}")
    print(f"  Return on Equity: {format_pct(f.roe * 100 if f.roe is not None else None, include_plus=False)}")

    print("\n--- Financials ---")
    print(f"  Revenue:          {format_currency(f.total_revenue)}")
    print(f"  Gross Profit:     {format_currency(f.gross_profit)}")
    print(f"  Operating Income: {format_currency(f.operating_income)}")
    print(f"  Net Income:       {format_currency(f.net_income)}")
    print(f"  EPS (Trailing):   {format_currency(f.trailing_eps) if f.trailing_eps is not None else 'N/A'}")

    print("\n--- Cash Flow Statement Highlights ---")
    print(f"  Operating Cash Flow: {format_currency(f.operating_cash_flow)}")
    print(f"  Capital Expenditure: {format_currency(f.capital_expenditure)}")
    print(f"  Free Cash Flow:      {format_currency(f.free_cash_flow)}")

    if cf is not None and not cf.empty:
        key_items = ["Operating Cash Flow", "Capital Expenditure", "Free Cash Flow", "Investing Cash Flow", "Financing Cash Flow", "End Cash Position"]
        available_items = [item for item in key_items if item in cf.index]
        if available_items:
            print("\n--- Cash Flow Statement (Recent Fiscal Years) ---")
            cols = [c.strftime("%Y-%m-%d") if hasattr(c, "strftime") else str(c)[:10] for c in cf.columns[:4]]
            hdr = f"  {'Line Item':<26}" + "".join(f"{c:>14}" for c in cols)
            print(hdr)
            print("  " + "-" * (len(hdr) - 2))
            for item in available_items:
                row_str = f"  {item:<26}"
                for col_idx in range(len(cols)):
                    val = cf.loc[item].iloc[col_idx]
                    row_str += f"{format_currency(float(val)):>14}" if pd.notnull(val) else f"{'N/A':>14}"
                print(row_str)

    print("\n--- Performance Returns ---")
    print(f"  Return to Date (YTD): {format_pct(p.ytd)}")
    print(f"  1-Year Return:        {format_pct(p.one_year)}")
    print(f"  5-Year Return:        {format_pct(p.five_year)}")
    print(f"  10-Year Return:       {format_pct(p.ten_year)}")

    print(f"\n--- Historical Data (Last {len(h)} Trading Days) ---")
    if h is not None and not h.empty:
        header = f"  {'Date':<12} {'Open':>10} {'High':>10} {'Low':>10} {'Close':>10} {'Volume':>14}"
        print(header)
        print("  " + "-" * (len(header) - 2))
        for idx, row in h.iterrows():
            date_str = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]
            open_val = f"${row['Open']:.2f}"
            high_val = f"${row['High']:.2f}"
            low_val = f"${row['Low']:.2f}"
            close_val = f"${row['Close']:.2f}"
            vol_val = f"{int(row['Volume']):,}"
            print(f"  {date_str:<12} {open_val:>10} {high_val:>10} {low_val:>10} {close_val:>10} {vol_val:>14}")
    else:
        print("  No historical data available.")


def export_to_excel(stock_data_list: list[StockData], output_path: str = "stocks_report.xlsx"):
    """Export one or multiple StockData reports into a formatted Excel (.xlsx) workbook."""
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    except ImportError:
        print("\n[ERROR] 'openpyxl' is required for Excel export. Run: pip install openpyxl", file=sys.stderr)
        return

    if not stock_data_list:
        print("[WARNING] No stock data available to export to Excel.", file=sys.stderr)
        return

    # 1. Summary sheet rows
    summary_rows = []
    for item in stock_data_list:
        q = item.quote
        f = item.fundamentals
        p = item.performance
        summary_rows.append({
            "Symbol": q.symbol,
            "Company Name": q.name,
            "Price": q.price,
            "Currency": q.currency,
            "Change ($)": q.change,
            "Change (%)": q.percent_change,
            "Earnings Date": f.earnings_date or "N/A",
            "Market Cap": f.market_cap,
            "P/E Ratio": f.trailing_pe,
            "Forward P/E": f.forward_pe,
            "Dividend Yield (%)": round(f.dividend_yield, 2) if f.dividend_yield is not None else None,
            "Gross Margin (%)": round(f.gross_margin * 100, 2) if f.gross_margin is not None else None,
            "Operating Margin (%)": round(f.operating_margin * 100, 2) if f.operating_margin is not None else None,
            "Net Profit Margin (%)": round(f.profit_margin * 100, 2) if f.profit_margin is not None else None,
            "EBITDA Margin (%)": round(f.ebitda_margin * 100, 2) if f.ebitda_margin is not None else None,
            "ROA (%)": round(f.roa * 100, 2) if f.roa is not None else None,
            "ROE (%)": round(f.roe * 100, 2) if f.roe is not None else None,
            "Total Revenue": f.total_revenue,
            "Gross Profit": f.gross_profit,
            "Operating Income": f.operating_income,
            "Net Income": f.net_income,
            "Operating Cash Flow": f.operating_cash_flow,
            "Capital Expenditure": f.capital_expenditure,
            "Free Cash Flow": f.free_cash_flow,
            "YTD Return (%)": p.ytd,
            "1-Year Return (%)": p.one_year,
            "5-Year Return (%)": p.five_year,
            "10-Year Return (%)": p.ten_year,
        })

    summary_df = pd.DataFrame(summary_rows)

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="Overview", index=False)

        # Cash Flow & History sheets per symbol
        for item in stock_data_list:
            sym = item.quote.symbol
            # Cash Flow sheet
            if item.cash_flow_statement is not None and not item.cash_flow_statement.empty:
                sheet_cf_name = f"{sym[:20]}_CashFlow"
                item.cash_flow_statement.to_excel(writer, sheet_name=sheet_cf_name, index=True)

            # Historical data sheet
            if item.historical_data is not None and not item.historical_data.empty:
                sheet_hist_name = f"{sym[:20]}_History"
                hist_copy = item.historical_data.copy()
                if hasattr(hist_copy.index, "tz") and hist_copy.index.tz is not None:
                    hist_copy.index = hist_copy.index.tz_localize(None)
                for col in hist_copy.select_dtypes(include=["datetimetz"]).columns:
                    hist_copy[col] = hist_copy[col].dt.tz_localize(None)
                hist_copy.index.name = "Date"
                hist_copy.to_excel(writer, sheet_name=sheet_hist_name, index=True)

        wb = writer.book
        header_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        regular_font = Font(name="Calibri", size=10)
        thin_border = Border(
            left=Side(style="thin", color="D9D9D9"),
            right=Side(style="thin", color="D9D9D9"),
            top=Side(style="thin", color="D9D9D9"),
            bottom=Side(style="thin", color="D9D9D9"),
        )

        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            for cell in ws[1]:
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

            for row in ws.iter_rows(min_row=2):
                for cell in row:
                    cell.font = regular_font
                    cell.border = thin_border

            for col in ws.columns:
                max_len = 0
                col_letter = col[0].column_letter
                for cell in col:
                    val_str = str(cell.value or "")
                    max_len = max(max_len, len(val_str))
                ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    print(f"\n[EXCEL] Successfully exported financial report for {len(stock_data_list)} stock(s) to '{output_path}'")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Fetch and display financial stock reports.")
    parser.add_argument(
        "--provider",
        "-p",
        choices=["yahoo", "robinhood"],
        default="yahoo",
        help="Stock data provider backend (default: yahoo)",
    )
    parser.add_argument(
        "symbols",
        nargs="*",
        default=["AAPL"],
        help="Stock ticker symbols to fetch (e.g. AAPL MSFT GOOGL)",
    )
    parser.add_argument(
        "--history-days",
        "-d",
        type=int,
        default=5,
        help="Number of historical trading days to display (default: 5)",
    )
    parser.add_argument(
        "--excel",
        "--export-excel",
        nargs="?",
        const="stocks_report.xlsx",
        default=None,
        metavar="FILE",
        help="Export fetched stock data to an Excel file (.xlsx) (default: stocks_report.xlsx)",
    )

    args = parser.parse_args()

    try:
        provider = get_stock_provider(args.provider)
    except Exception as e:
        print(f"[ERROR] Failed to initialize provider '{args.provider}': {e}", file=sys.stderr)
        sys.exit(1)

    all_stock_data = []
    for sym in args.symbols:
        try:
            stock_data = provider.get_stock_data(sym, history_days=args.history_days)
            print_stock_report(stock_data)
            all_stock_data.append(stock_data)
        except Exception as e:
            print(f"\n[ERROR] Failed to fetch data for {sym}: {e}", file=sys.stderr)

    if args.excel and all_stock_data:
        export_to_excel(all_stock_data, args.excel)
