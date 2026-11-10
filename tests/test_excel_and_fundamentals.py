import os
import tempfile
import unittest
import pandas as pd
import openpyxl
from stock_fetcher import (
    StockQuote,
    StockFundamentals,
    StockPerformance,
    StockData,
    export_to_excel,
)


class TestExcelAndFundamentals(unittest.TestCase):
    def test_stock_fundamentals_and_cashflow(self):
        funds = StockFundamentals(
            market_cap=3e12,
            earnings_date="2027-01-28",
            gross_margin=0.45,
            operating_margin=0.30,
            profit_margin=0.25,
            ebitda_margin=0.35,
            roa=0.20,
            roe=1.20,
            free_cash_flow=1e11,
            operating_cash_flow=1.2e11,
            capital_expenditure=-2e10,
        )
        self.assertEqual(funds.earnings_date, "2027-01-28")
        self.assertEqual(funds.gross_margin, 0.45)
        self.assertEqual(funds.free_cash_flow, 1e11)

    def test_export_to_excel(self):
        quote = StockQuote(
            symbol="TEST",
            name="Test Corp",
            price=123.45,
            change=2.34,
            percent_change=1.93,
            currency="USD",
            timestamp="2026-11-10 12:00:00",
        )
        funds = StockFundamentals(
            market_cap=1e10,
            trailing_pe=25.0,
            earnings_date="2026-12-01",
            gross_margin=0.50,
            operating_margin=0.25,
            profit_margin=0.20,
            free_cash_flow=5e8,
            operating_cash_flow=6e8,
            capital_expenditure=-1e8,
        )
        perf = StockPerformance(ytd=12.5, one_year=20.0, five_year=75.0)

        # Timezone-aware history dataframe
        dates = pd.date_range("2026-11-01", periods=5, freq="D", tz="America/New_York")
        hist = pd.DataFrame(
            {
                "Open": [120.0] * 5,
                "High": [125.0] * 5,
                "Low": [119.0] * 5,
                "Close": [123.45] * 5,
                "Volume": [1000000] * 5,
            },
            index=dates,
        )

        cash_flow_stmt = pd.DataFrame(
            {
                "2026-09-30": [6e8, -1e8, 5e8],
                "2025-09-30": [5e8, -8e7, 4.2e8],
            },
            index=["Operating Cash Flow", "Capital Expenditure", "Free Cash Flow"],
        )
        cash_flow_stmt.index.name = "Line Item"

        stock_data = StockData(
            quote=quote,
            fundamentals=funds,
            performance=perf,
            historical_data=hist,
            cash_flow_statement=cash_flow_stmt,
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            export_to_excel([stock_data], output_path=tmp_path)
            self.assertTrue(os.path.exists(tmp_path))

            wb = openpyxl.load_workbook(tmp_path)
            self.assertIn("Overview", wb.sheetnames)
            self.assertIn("TEST_CashFlow", wb.sheetnames)
            self.assertIn("TEST_History", wb.sheetnames)

            overview_ws = wb["Overview"]
            headers = [cell.value for cell in overview_ws[1]]
            self.assertIn("Symbol", headers)
            self.assertIn("Earnings Date", headers)
            self.assertIn("Gross Margin (%)", headers)
            self.assertIn("Free Cash Flow", headers)

            row2 = [cell.value for cell in overview_ws[2]]
            self.assertEqual(row2[headers.index("Symbol")], "TEST")
            self.assertEqual(row2[headers.index("Earnings Date")], "2026-12-01")
            self.assertEqual(row2[headers.index("Gross Margin (%)")], 50.0)

            cf_ws = wb["TEST_CashFlow"]
            self.assertEqual(cf_ws["A2"].value, "Operating Cash Flow")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


if __name__ == "__main__":
    unittest.main()
