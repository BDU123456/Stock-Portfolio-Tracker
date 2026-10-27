"""Unit tests for the Stock Portfolio Performance Tracker.

All tests use local sample data and do not require internet access.
"""

from __future__ import annotations

import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

import portfolio


class ParseInputTests(unittest.TestCase):
    def test_valid_ticker(self):
        self.assertEqual(portfolio.parse_ticker(" aapl "), "AAPL")

    def test_empty_ticker(self):
        with self.assertRaises(ValueError):
            portfolio.parse_ticker("   ")

    def test_ticker_with_spaces(self):
        with self.assertRaises(ValueError):
            portfolio.parse_ticker("AA PL")

    def test_valid_purchase_price(self):
        self.assertEqual(portfolio.parse_purchase_price("120.555"), Decimal("120.56"))

    def test_zero_purchase_price(self):
        with self.assertRaises(ValueError):
            portfolio.parse_purchase_price("0")

    def test_negative_purchase_price(self):
        with self.assertRaises(ValueError):
            portfolio.parse_purchase_price("-10")

    def test_non_numeric_purchase_price(self):
        with self.assertRaises(ValueError):
            portfolio.parse_purchase_price("abc")

    def test_valid_quantity(self):
        self.assertEqual(portfolio.parse_quantity("15"), 15)

    def test_zero_quantity(self):
        with self.assertRaises(ValueError):
            portfolio.parse_quantity("0")

    def test_negative_quantity(self):
        with self.assertRaises(ValueError):
            portfolio.parse_quantity("-3")

    def test_fractional_quantity(self):
        with self.assertRaises(ValueError):
            portfolio.parse_quantity("2.5")


class CalculationTests(unittest.TestCase):
    def test_invested_amount(self):
        result = portfolio.invested_amount(Decimal("100.00"), 10)
        self.assertEqual(result, Decimal("1000.00"))

    def test_current_market_value(self):
        result = portfolio.current_market_value(Decimal("120.00"), 10)
        self.assertEqual(result, Decimal("1200.00"))

    def test_positive_profit(self):
        invested = Decimal("1000.00")
        market = Decimal("1200.00")
        self.assertEqual(portfolio.profit_or_loss(market, invested), Decimal("200.00"))

    def test_negative_loss(self):
        invested = Decimal("1000.00")
        market = Decimal("850.00")
        self.assertEqual(portfolio.profit_or_loss(market, invested), Decimal("-150.00"))

    def test_percentage_gain(self):
        result = portfolio.percentage_gain_loss(Decimal("200.00"), Decimal("1000.00"))
        self.assertEqual(result, Decimal("20.00"))

    def test_percentage_loss(self):
        result = portfolio.percentage_gain_loss(Decimal("-150.00"), Decimal("1000.00"))
        self.assertEqual(result, Decimal("-15.00"))

    def test_percentage_zero_invested_raises(self):
        with self.assertRaises(ZeroDivisionError):
            portfolio.percentage_gain_loss(Decimal("10.00"), Decimal("0.00"))


class PortfolioTotalsTests(unittest.TestCase):
    def setUp(self):
        self.holdings = {
            "AAPL": portfolio.create_holding("AAPL", Decimal("100.00"), 10),
            "MSFT": portfolio.create_holding("MSFT", Decimal("200.00"), 5),
        }
        self.prices = {
            "AAPL": Decimal("120.00"),
            "MSFT": Decimal("180.00"),
        }

    def test_totals_across_multiple_stocks(self):
        summary = portfolio.calculate_portfolio_performance(self.holdings, self.prices)
        # AAPL: invested 1000, market 1200, pl +200
        # MSFT: invested 1000, market 900, pl -100
        self.assertEqual(summary["total_invested_priced"], Decimal("2000.00"))
        self.assertEqual(summary["total_market_value"], Decimal("2100.00"))
        self.assertEqual(summary["total_profit_loss"], Decimal("100.00"))
        self.assertEqual(summary["overall_percentage"], Decimal("5.00"))
        self.assertEqual(summary["priced_count"], 2)
        self.assertEqual(summary["unpriced_count"], 0)

    def test_missing_stock_prices_excluded_from_totals(self):
        holdings = dict(self.holdings)
        holdings["GOOGL"] = portfolio.create_holding("GOOGL", Decimal("150.00"), 4)
        summary = portfolio.calculate_portfolio_performance(holdings, self.prices)

        self.assertEqual(summary["unpriced_count"], 1)
        self.assertEqual(summary["unpriced_tickers"], ["GOOGL"])
        self.assertEqual(summary["unpriced_invested"], Decimal("600.00"))
        self.assertEqual(summary["total_invested_priced"], Decimal("2000.00"))
        self.assertEqual(summary["total_invested_all"], Decimal("2600.00"))
        self.assertEqual(summary["total_market_value"], Decimal("2100.00"))

        googl = next(row for row in summary["rows"] if row["ticker"] == "GOOGL")
        self.assertFalse(googl["priced"])
        self.assertIsNone(googl["current_price"])
        self.assertIsNone(googl["market_value"])
        self.assertIsNone(googl["profit_loss"])
        self.assertIsNone(googl["percentage_change"])

    def test_unpriced_holding_does_not_use_purchase_price(self):
        holding = portfolio.create_holding("XYZ", Decimal("50.00"), 8)
        row = portfolio.calculate_holding_performance(holding, None)
        self.assertNotEqual(row["current_price"], holding["purchase_price"])
        self.assertIsNone(row["current_price"])


class DuplicateHoldingTests(unittest.TestCase):
    def test_skip_keeps_original(self):
        holdings = {}
        first = portfolio.create_holding("AAPL", Decimal("100.00"), 2)
        second = portfolio.create_holding("AAPL", Decimal("110.00"), 9)
        portfolio.add_or_update_holding(holdings, first, replace_existing=False)
        result = portfolio.add_or_update_holding(
            holdings, second, replace_existing=False
        )
        self.assertEqual(result, "skipped")
        self.assertEqual(holdings["AAPL"]["quantity"], 2)
        self.assertEqual(holdings["AAPL"]["purchase_price"], Decimal("100.00"))

    def test_update_replaces_holding(self):
        holdings = {}
        first = portfolio.create_holding("AAPL", Decimal("100.00"), 2)
        second = portfolio.create_holding("AAPL", Decimal("110.00"), 9)
        portfolio.add_or_update_holding(holdings, first, replace_existing=False)
        result = portfolio.add_or_update_holding(
            holdings, second, replace_existing=True
        )
        self.assertEqual(result, "updated")
        self.assertEqual(holdings["AAPL"]["quantity"], 9)


class CsvPriceLoadingTests(unittest.TestCase):
    def test_load_sample_dataset(self):
        prices = portfolio.load_prices_from_csv(portfolio.PRICE_FILE)
        self.assertIn("AAPL", prices)
        self.assertEqual(prices["AAPL"], Decimal("120.00"))
        self.assertEqual(prices["MSFT"], Decimal("220.00"))

    def test_empty_csv_returns_no_prices(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "empty.csv"
            path.write_text("Ticker,Current Price\n", encoding="utf-8")
            prices = portfolio.load_prices_from_csv(path)
            self.assertEqual(prices, {})

    def test_malformed_rows_are_skipped(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bad.csv"
            path.write_text(
                "Ticker,Current Price\n"
                "AAPL,120.00\n"
                "BADPRICE,not-a-number\n"
                ",50.00\n"
                "ZERO,0\n"
                "MSFT,220.00\n",
                encoding="utf-8",
            )
            prices = portfolio.load_prices_from_csv(path)
            self.assertEqual(set(prices), {"AAPL", "MSFT"})

    def test_missing_file_raises(self):
        missing = Path("this_file_does_not_exist_12345.csv")
        with self.assertRaises(FileNotFoundError):
            portfolio.load_prices_from_csv(missing)

    def test_ticker_only_csv_explains_missing_prices(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sp500.csv"
            path.write_text("Ticker\nAAPL\nMSFT\n", encoding="utf-8")
            with self.assertRaises(ValueError) as context:
                portfolio.load_prices_from_csv(path)
            self.assertIn("Current Price", str(context.exception))
            self.assertIn("S&P 500", str(context.exception))


class ExportCsvTests(unittest.TestCase):
    def test_export_writes_headers_and_na_for_missing_price(self):
        holdings = {
            "AAPL": portfolio.create_holding("AAPL", Decimal("100.00"), 10),
            "ZZZ": portfolio.create_holding("ZZZ", Decimal("40.00"), 3),
        }
        prices = {"AAPL": Decimal("120.00")}
        summary = portfolio.calculate_portfolio_performance(holdings, prices)

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "portfolio_summary.csv"
            portfolio.export_summary_csv(summary, path)
            text = path.read_text(encoding="utf-8")
            self.assertIn("Ticker,Purchase Price,Quantity,Current Price", text)
            self.assertIn("AAPL,100.00,10,120.00,1000.00,1200.00,200.00,20.00", text)
            self.assertIn("ZZZ,40.00,3,N/A,120.00,N/A,N/A,N/A", text)
            self.assertIn("TOTAL (priced holdings)", text)
            self.assertIn("UNPRICED HOLDINGS", text)


if __name__ == "__main__":
    unittest.main()
