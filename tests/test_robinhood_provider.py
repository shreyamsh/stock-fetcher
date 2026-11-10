import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
from stock_fetcher import RobinhoodProvider, get_stock_provider, StockData, StockQuote


class TestRobinhoodProvider(unittest.TestCase):
    def setUp(self):
        self.provider = RobinhoodProvider(
            username="test_user@example.com",
            password="test_password",
            mfa_secret="JBSWY3DPEHPK3PXP" # Base32 test secret
        )

    def test_factory_creation(self):
        provider = get_stock_provider("robinhood")
        self.assertIsInstance(provider, RobinhoodProvider)

    @patch("robin_stocks.robinhood.login")
    @patch("pyotp.TOTP.now")
    def test_authenticate_with_totp(self, mock_totp_now, mock_login):
        mock_totp_now.return_value = "123456"
        mock_login.return_value = {"access_token": "mock_token"}

        self.provider.authenticate()

        self.assertTrue(self.provider._authenticated)
        mock_totp_now.assert_called_once()
        mock_login.assert_called_once_with(
            username="test_user@example.com",
            password="test_password",
            mfa_code="123456",
            expiresIn=86400,
            store_session=True,
        )

        # Calling authenticate again should not re-login (session cached)
        self.provider.authenticate()
        self.assertEqual(mock_login.call_count, 1)

    @patch("robin_stocks.robinhood.login")
    @patch("robin_stocks.robinhood.stocks.get_name_by_symbol")
    @patch("robin_stocks.robinhood.stocks.get_stock_quote_by_symbol")
    def test_get_quote(self, mock_quote, mock_name, mock_login):
        mock_login.return_value = {"access_token": "mock_token"}
        mock_quote.return_value = {
            "symbol": "AAPL",
            "last_trade_price": "150.00",
            "previous_close": "145.00",
            "updated_at": "2026-11-09T16:00:00Z"
        }
        mock_name.return_value = "Apple Inc."

        quote = self.provider.get_quote("AAPL")

        self.assertEqual(quote.symbol, "AAPL")
        self.assertEqual(quote.name, "Apple Inc.")
        self.assertEqual(quote.price, 150.00)
        self.assertEqual(quote.change, 5.00)
        self.assertEqual(quote.percent_change, 3.45) # 5.0 / 145.0 * 100 = 3.448... -> 3.45
        self.assertEqual(quote.currency, "USD")
        self.assertEqual(quote.timestamp, "2026-11-09T16:00:00Z")

    @patch("robin_stocks.robinhood.login")
    @patch("robin_stocks.robinhood.stocks.get_stock_historicals")
    def test_get_historical_data(self, mock_hist, mock_login):
        mock_login.return_value = {"access_token": "mock_token"}
        mock_hist.return_value = [
            {
                "begins_at": "2026-11-05T00:00:00Z",
                "open_price": "140.00",
                "high_price": "145.00",
                "low_price": "139.00",
                "close_price": "142.50",
                "volume": "50000000",
                "session": "reg",
                "interpolated": False,
                "symbol": "AAPL",
            },
            {
                "begins_at": "2026-11-06T00:00:00Z",
                "open_price": "143.00",
                "high_price": "151.00",
                "low_price": "142.00",
                "close_price": "150.00",
                "volume": "60000000",
                "session": "reg",
                "interpolated": False,
                "symbol": "AAPL",
            }
        ]

        df = self.provider.get_historical_data("AAPL", period="5d")

        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(len(df), 2)
        self.assertListEqual(list(df.columns), ["Open", "High", "Low", "Close", "Volume"])
        self.assertIsInstance(df.index, pd.DatetimeIndex)
        self.assertEqual(df["Close"].iloc[-1], 150.00)
        self.assertEqual(df["Volume"].iloc[-1], 60000000)

    @patch("robin_stocks.robinhood.login")
    @patch("robin_stocks.robinhood.stocks.get_fundamentals")
    @patch.object(RobinhoodProvider, "get_quote")
    @patch.object(RobinhoodProvider, "get_historical_data")
    def test_get_stock_data(self, mock_hist, mock_quote, mock_funds, mock_login):
        mock_login.return_value = {"access_token": "mock_token"}
        mock_quote.return_value = StockQuote(
            symbol="AAPL",
            name="Apple Inc.",
            price=150.00,
            change=5.00,
            percent_change=3.45,
            currency="USD",
            timestamp="2026-11-09 16:00:00"
        )
        mock_funds.return_value = [{
            "market_cap": "2500000000000",
            "pe_ratio": "28.5",
            "dividend_yield": "0.55",
            "symbol": "AAPL"
        }]

        # Create dummy 5-year historical dataframe
        dates = pd.date_range("2021-01-01", periods=10, freq="200D")
        mock_hist.return_value = pd.DataFrame(
            {
                "Open": [100.0 + i for i in range(10)],
                "High": [105.0 + i for i in range(10)],
                "Low": [95.0 + i for i in range(10)],
                "Close": [100.0 + (i * 5) for i in range(10)],
                "Volume": [1000000 for _ in range(10)],
            },
            index=dates,
        )

        stock_data = self.provider.get_stock_data("AAPL", history_days=3)

        self.assertIsInstance(stock_data, StockData)
        self.assertEqual(stock_data.quote.symbol, "AAPL")
        self.assertEqual(stock_data.fundamentals.market_cap, 2500000000000.0)
        self.assertEqual(stock_data.fundamentals.trailing_pe, 28.5)
        self.assertEqual(stock_data.fundamentals.dividend_yield, 0.55)
        self.assertEqual(len(stock_data.historical_data), 3)


if __name__ == "__main__":
    unittest.main()
