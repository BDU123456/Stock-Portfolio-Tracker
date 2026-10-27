"""
Stock Portfolio Performance Tracker

A beginner-friendly console app that stores stock holdings, calculates
invested capital, current value, profit/loss, and percent change, then
exports a summary CSV.

Current prices come from the local sample file stock_prices.csv by default.
Optional live prices via yfinance are available if that package is installed.
Sample CSV prices are fictional examples for practice, not live market data.
"""

from __future__ import annotations

import csv
import sys
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent
PRICE_FILE = BASE_DIR / "stock_prices.csv"
SUMMARY_FILE = BASE_DIR / "portfolio_summary.csv"

MONEY = Decimal("0.01")
PERCENT = Decimal("0.01")
PRICE_SOURCE_CSV = "csv"
PRICE_SOURCE_ONLINE = "online"

UNAVAILABLE = "N/A"


# ---------------------------------------------------------------------------
# Helpers for money and input parsing
# ---------------------------------------------------------------------------

def quantize_money(value: Decimal) -> Decimal:
    """Round a money amount to two decimal places."""
    return value.quantize(MONEY, rounding=ROUND_HALF_EVEN)


def quantize_percent(value: Decimal) -> Decimal:
    """Round a percentage to two decimal places."""
    return value.quantize(PERCENT, rounding=ROUND_HALF_EVEN)


def parse_ticker(raw: str) -> str:
    """Validate and normalize a ticker symbol."""
    ticker = raw.strip().upper()
    if not ticker:
        raise ValueError("Ticker symbol cannot be empty.")
    if any(char.isspace() for char in ticker):
        raise ValueError("Ticker symbol cannot contain spaces.")
    return ticker


def parse_purchase_price(raw: str) -> Decimal:
    """Parse a purchase price. Must be a positive number."""
    try:
        price = Decimal(raw.strip())
    except (InvalidOperation, AttributeError):
        raise ValueError("Purchase price must be a number.") from None
    if price <= 0:
        raise ValueError("Purchase price must be greater than zero.")
    return quantize_money(price)


def parse_quantity(raw: str) -> int:
    """Parse share quantity. Must be a positive integer."""
    text = raw.strip()
    if not text:
        raise ValueError("Share quantity cannot be empty.")
    try:
        quantity = int(text)
    except ValueError:
        raise ValueError("Share quantity must be a whole number.") from None
    if quantity <= 0:
        raise ValueError("Share quantity must be a positive integer.")
    return quantity


def prompt_until_valid(message: str, parser):
    """Ask the user for input until the parser accepts it."""
    while True:
        try:
            return parser(input(message))
        except ValueError as error:
            print(f"  Invalid input: {error} Please try again.")
        except EOFError:
            print("\nInput ended unexpectedly.")
            raise


# ---------------------------------------------------------------------------
# Holdings (dictionary storage)
# ---------------------------------------------------------------------------

def create_holding(ticker: str, purchase_price: Decimal, quantity: int) -> dict:
    """Build one holding dictionary."""
    return {
        "ticker": ticker,
        "purchase_price": purchase_price,
        "quantity": quantity,
    }


def add_or_update_holding(
    holdings: dict[str, dict],
    holding: dict,
    replace_existing: bool,
) -> str:
    """
    Insert a holding into the portfolio dictionary.

    Returns 'added', 'updated', or 'skipped'.
    Existing holdings are never overwritten unless replace_existing is True.
    """
    ticker = holding["ticker"]
    existed = ticker in holdings
    if existed and not replace_existing:
        return "skipped"
    holdings[ticker] = holding
    return "updated" if existed else "added"


def prompt_add_holding(holdings: dict[str, dict]) -> None:
    """Collect one holding from the user and store it in holdings."""
    ticker = prompt_until_valid("Ticker symbol (for example AAPL): ", parse_ticker)
    if ticker in holdings:
        existing = holdings[ticker]
        print(
            f"  {ticker} is already in the portfolio "
            f"(purchase price {existing['purchase_price']}, "
            f"quantity {existing['quantity']})."
        )
        choice = input("  Update this holding? (y/n): ").strip().lower()
        if choice not in {"y", "yes"}:
            print("  Existing holding was left unchanged.")
            return
        replace_existing = True
    else:
        replace_existing = False

    purchase_price = prompt_until_valid(
        "Purchase price per share: ", parse_purchase_price
    )
    quantity = prompt_until_valid("Number of shares: ", parse_quantity)
    holding = create_holding(ticker, purchase_price, quantity)
    result = add_or_update_holding(holdings, holding, replace_existing)
    if result == "updated":
        print(f"  Updated holding for {ticker}.")
    else:
        print(f"  Added {ticker} ({quantity} shares at {purchase_price}).")


# ---------------------------------------------------------------------------
# Price loading
# ---------------------------------------------------------------------------

def load_prices_from_csv(path: Path) -> dict[str, Decimal]:
    """
    Load ticker -> current price from a CSV file.

    Expected headers: Ticker, Current Price
    Malformed rows are skipped. Missing files raise FileNotFoundError.
    """
    prices: dict[str, Decimal] = {}
    skipped = 0

    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            return prices

        field_map = {name.strip().lower(): name for name in reader.fieldnames if name}
        ticker_key = field_map.get("ticker")
        price_key = field_map.get("current price") or field_map.get("price")

        if ticker_key is None:
            raise ValueError("CSV is missing a Ticker column.")
        if price_key is None:
            raise ValueError(
                "CSV is missing a Current Price column. "
                "If the file only lists ticker symbols (for example an S&P 500 "
                "constituents list), add prices to the dataset or use optional "
                "online retrieval."
            )

        for row in reader:
            raw_ticker = (row.get(ticker_key) or "").strip()
            raw_price = (row.get(price_key) or "").strip()
            if not raw_ticker and not raw_price:
                continue
            try:
                ticker = parse_ticker(raw_ticker)
                price = parse_purchase_price(raw_price)
            except ValueError:
                skipped += 1
                continue
            prices[ticker] = price

    if skipped:
        print(f"  Skipped {skipped} malformed row(s) in {path.name}.")
    return prices


def fetch_online_price(ticker: str) -> Optional[Decimal]:
    """
    Optionally fetch one live price with yfinance.

    Returns None when the library is missing, the network fails, or no
    price is available. Never falls back to the purchase price.
    """
    try:
        import yfinance as yf  # type: ignore
    except ImportError:
        raise RuntimeError(
            "yfinance is not installed. Leave the price source on sample CSV, "
            "or install it with: pip install yfinance"
        ) from None

    try:
        stock = yf.Ticker(ticker)
        price = None
        try:
            fast = stock.fast_info
            price = fast.get("lastPrice") or fast.get("last_price") or fast.get("regularMarketPrice")
        except Exception:
            price = None
        if price is None:
            info = stock.info or {}
            price = info.get("regularMarketPrice") or info.get("currentPrice")
        if price is None:
            return None
        value = Decimal(str(price))
        if value <= 0:
            return None
        return quantize_money(value)
    except Exception:
        return None


def load_prices_for_holdings(
    holdings: dict[str, dict],
    source: str,
    csv_path: Path,
) -> tuple[dict[str, Decimal], list[str]]:
    """
    Return (prices, notes). notes contains user-facing warnings.

    Holdings whose prices cannot be found are omitted from the prices dict.
    """
    notes: list[str] = []
    prices: dict[str, Decimal] = {}

    if source == PRICE_SOURCE_CSV:
        notes.append(
            "Using sample prices from stock_prices.csv. "
            "These values are fictional examples, not live market prices."
        )
        try:
            catalog = load_prices_from_csv(csv_path)
        except FileNotFoundError:
            notes.append(f"Price file not found: {csv_path}")
            return prices, notes
        except ValueError as error:
            notes.append(str(error))
            return prices, notes

        for ticker in holdings:
            if ticker in catalog:
                prices[ticker] = catalog[ticker]
        return prices, notes

    notes.append("Using optional online prices via yfinance.")
    try:
        import yfinance  # noqa: F401  # type: ignore
    except ImportError:
        notes.append(
            "yfinance is not installed, so no live prices were retrieved. "
            "Install it with: pip install yfinance"
        )
        return prices, notes

    for ticker in holdings:
        current = fetch_online_price(ticker)
        if current is None:
            notes.append(f"No live price available for {ticker}.")
        else:
            prices[ticker] = current
    return prices, notes


# ---------------------------------------------------------------------------
# Calculations (kept separate from input/output for unit testing)
# ---------------------------------------------------------------------------

def invested_amount(purchase_price: Decimal, quantity: int) -> Decimal:
    """Invested Amount = Purchase Price x Quantity."""
    return quantize_money(purchase_price * Decimal(quantity))


def current_market_value(current_price: Decimal, quantity: int) -> Decimal:
    """Current Market Value = Current Price x Quantity."""
    return quantize_money(current_price * Decimal(quantity))


def profit_or_loss(market_value: Decimal, invested: Decimal) -> Decimal:
    """Profit/Loss = Current Market Value - Invested Amount."""
    return quantize_money(market_value - invested)


def percentage_gain_loss(pl_amount: Decimal, invested: Decimal) -> Decimal:
    """Percentage Gain/Loss = (Profit/Loss / Invested Amount) x 100."""
    if invested == 0:
        raise ZeroDivisionError("Invested amount cannot be zero.")
    return quantize_percent((pl_amount / invested) * Decimal("100"))


def calculate_holding_performance(
    holding: dict,
    current_price: Optional[Decimal],
) -> dict:
    """
    Calculate performance for one holding.

    If current_price is None, money fields that depend on market price
    are left as None so callers can treat the holding as unpriced.
    """
    invested = invested_amount(holding["purchase_price"], holding["quantity"])
    result = {
        "ticker": holding["ticker"],
        "purchase_price": quantize_money(holding["purchase_price"]),
        "quantity": holding["quantity"],
        "current_price": current_price,
        "invested_amount": invested,
        "market_value": None,
        "profit_loss": None,
        "percentage_change": None,
        "priced": current_price is not None,
    }
    if current_price is None:
        return result

    market = current_market_value(current_price, holding["quantity"])
    pl_amount = profit_or_loss(market, invested)
    result["market_value"] = market
    result["profit_loss"] = pl_amount
    result["percentage_change"] = percentage_gain_loss(pl_amount, invested)
    return result


def calculate_portfolio_performance(
    holdings: dict[str, dict],
    prices: dict[str, Decimal],
) -> dict:
    """
    Calculate per-holding rows and portfolio totals.

    Unpriced holdings are listed but excluded from market-value totals.
    """
    rows = []
    for ticker, holding in holdings.items():
        current = prices.get(ticker)
        rows.append(calculate_holding_performance(holding, current))

    priced_rows = [row for row in rows if row["priced"]]
    unpriced_rows = [row for row in rows if not row["priced"]]

    total_invested_all = sum(
        (row["invested_amount"] for row in rows), Decimal("0.00")
    )
    total_invested_priced = sum(
        (row["invested_amount"] for row in priced_rows), Decimal("0.00")
    )
    total_market = sum(
        (row["market_value"] for row in priced_rows), Decimal("0.00")
    )
    total_pl = quantize_money(total_market - total_invested_priced)
    if total_invested_priced > 0:
        overall_pct = percentage_gain_loss(total_pl, total_invested_priced)
    else:
        overall_pct = None

    unpriced_invested = sum(
        (row["invested_amount"] for row in unpriced_rows), Decimal("0.00")
    )

    return {
        "rows": rows,
        "total_invested_all": quantize_money(total_invested_all),
        "total_invested_priced": quantize_money(total_invested_priced),
        "total_market_value": quantize_money(total_market),
        "total_profit_loss": total_pl,
        "overall_percentage": overall_pct,
        "unpriced_count": len(unpriced_rows),
        "unpriced_tickers": [row["ticker"] for row in unpriced_rows],
        "unpriced_invested": quantize_money(unpriced_invested),
        "priced_count": len(priced_rows),
    }


# ---------------------------------------------------------------------------
# Display and CSV export
# ---------------------------------------------------------------------------

def format_money(value: Optional[Decimal]) -> str:
    if value is None:
        return UNAVAILABLE
    sign = "-" if value < 0 else ""
    return f"{sign}${abs(value):,.2f}"


def format_signed_money(value: Optional[Decimal]) -> str:
    if value is None:
        return UNAVAILABLE
    if value > 0:
        return f"+${value:,.2f}"
    if value < 0:
        return f"-${abs(value):,.2f}"
    return f"${value:,.2f}"


def format_percent(value: Optional[Decimal]) -> str:
    if value is None:
        return UNAVAILABLE
    if value > 0:
        return f"+{value:.2f}%"
    if value < 0:
        return f"{value:.2f}%"
    return f"{value:.2f}%"


def format_price(value: Optional[Decimal]) -> str:
    if value is None:
        return UNAVAILABLE
    return f"${value:,.2f}"


def build_report_lines(summary: dict, notes: list[str]) -> list[str]:
    """Build console report lines from a calculated summary."""
    lines = [
        "",
        "=" * 96,
        "STOCK PORTFOLIO PERFORMANCE REPORT",
        "=" * 96,
    ]
    for note in notes:
        lines.append(note)
    lines.append("-" * 96)
    lines.append(
        f"{'Ticker':<8} {'Purchase':>12} {'Qty':>8} {'Current':>12} "
        f"{'Invested':>14} {'Market Value':>14} {'Profit/Loss':>14} {'Change':>10}"
    )
    lines.append("-" * 96)

    if not summary["rows"]:
        lines.append("No holdings in the portfolio yet.")
    else:
        for row in summary["rows"]:
            lines.append(
                f"{row['ticker']:<8} "
                f"{format_price(row['purchase_price']):>12} "
                f"{row['quantity']:>8} "
                f"{format_price(row['current_price']):>12} "
                f"{format_money(row['invested_amount']):>14} "
                f"{format_money(row['market_value']):>14} "
                f"{format_signed_money(row['profit_loss']):>14} "
                f"{format_percent(row['percentage_change']):>10}"
            )

    lines.append("-" * 96)
    if summary["unpriced_count"]:
        tickers = ", ".join(summary["unpriced_tickers"])
        lines.append(
            f"Incomplete data: {summary['unpriced_count']} holding(s) could not "
            f"be priced ({tickers})."
        )
        lines.append(
            f"Unpriced invested capital excluded from performance totals: "
            f"{format_money(summary['unpriced_invested'])}"
        )
        lines.append(
            "Market value, profit/loss, and overall percentage use only holdings "
            "with a current price. Missing prices are never replaced with the "
            "purchase price."
        )
        lines.append(
            f"Invested capital of priced holdings: "
            f"{format_money(summary['total_invested_priced'])}"
        )
        lines.append(
            f"Invested capital of all holdings (including unpriced): "
            f"{format_money(summary['total_invested_all'])}"
        )
    else:
        lines.append(
            f"Total invested capital: {format_money(summary['total_invested_priced'])}"
        )

    lines.append(
        f"Total current market value: {format_money(summary['total_market_value'])}"
    )
    lines.append(
        f"Total profit/loss: {format_signed_money(summary['total_profit_loss'])}"
    )
    lines.append(
        f"Overall percentage gain/loss: {format_percent(summary['overall_percentage'])}"
    )
    lines.append("=" * 96)
    return lines


def print_report(summary: dict, notes: list[str]) -> None:
    for line in build_report_lines(summary, notes):
        print(line)


def csv_cell(value: Optional[Decimal], as_percent: bool = False) -> str:
    if value is None:
        return UNAVAILABLE
    if as_percent:
        return f"{value:.2f}"
    return f"{value:.2f}"


def export_summary_csv(summary: dict, path: Path) -> None:
    """Write the latest portfolio calculation. Overwrites any previous summary."""
    fieldnames = [
        "Ticker",
        "Purchase Price",
        "Quantity",
        "Current Price",
        "Invested Amount",
        "Market Value",
        "Profit/Loss",
        "Percentage Change",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in summary["rows"]:
            writer.writerow(
                {
                    "Ticker": row["ticker"],
                    "Purchase Price": csv_cell(row["purchase_price"]),
                    "Quantity": row["quantity"],
                    "Current Price": csv_cell(row["current_price"]),
                    "Invested Amount": csv_cell(row["invested_amount"]),
                    "Market Value": csv_cell(row["market_value"]),
                    "Profit/Loss": csv_cell(row["profit_loss"]),
                    "Percentage Change": csv_cell(
                        row["percentage_change"], as_percent=True
                    ),
                }
            )
        writer.writerow({})
        writer.writerow(
            {
                "Ticker": "TOTAL (priced holdings)",
                "Purchase Price": "",
                "Quantity": "",
                "Current Price": "",
                "Invested Amount": csv_cell(summary["total_invested_priced"]),
                "Market Value": csv_cell(summary["total_market_value"]),
                "Profit/Loss": csv_cell(summary["total_profit_loss"]),
                "Percentage Change": csv_cell(
                    summary["overall_percentage"], as_percent=True
                ),
            }
        )
        if summary["unpriced_count"]:
            writer.writerow(
                {
                    "Ticker": "UNPRICED HOLDINGS",
                    "Purchase Price": "",
                    "Quantity": summary["unpriced_count"],
                    "Current Price": UNAVAILABLE,
                    "Invested Amount": csv_cell(summary["unpriced_invested"]),
                    "Market Value": UNAVAILABLE,
                    "Profit/Loss": UNAVAILABLE,
                    "Percentage Change": UNAVAILABLE,
                }
            )


def compute_and_maybe_save(
    holdings: dict[str, dict],
    price_source: str,
    save: bool,
) -> Optional[dict]:
    """Calculate performance, print it, and optionally save the latest CSV."""
    if not holdings:
        print("The portfolio is empty. Add a stock holding first.")
        return None

    prices, notes = load_prices_for_holdings(holdings, price_source, PRICE_FILE)
    summary = calculate_portfolio_performance(holdings, prices)
    print_report(summary, notes)

    if save:
        try:
            export_summary_csv(summary, SUMMARY_FILE)
        except OSError as error:
            print(f"Could not save {SUMMARY_FILE.name}: {error}")
        else:
            print(
                f"Latest portfolio summary saved to {SUMMARY_FILE.name}. "
                "This file is overwritten each time and is not a trade history."
            )
    return summary


def change_price_source(current: str) -> str:
    print()
    print("Price source:")
    print("  1. Sample CSV (default, works offline, fictional example prices)")
    print("  2. Optional online retrieval with yfinance")
    choice = input("Choose 1 or 2: ").strip()
    if choice == "2":
        print("Online prices are optional and need internet access plus yfinance.")
        return PRICE_SOURCE_ONLINE
    print("Using sample CSV prices.")
    return PRICE_SOURCE_CSV


def print_menu(price_source: str) -> None:
    label = (
        "sample CSV (fictional prices)"
        if price_source == PRICE_SOURCE_CSV
        else "optional online (yfinance)"
    )
    print()
    print("Stock Portfolio Performance Tracker")
    print(f"Price source: {label}")
    print("1. Add a stock holding")
    print("2. View portfolio performance")
    print("3. Save portfolio summary to CSV")
    print("4. Change price source")
    print("5. Exit")


def main() -> int:
    holdings: dict[str, dict] = {}
    price_source = PRICE_SOURCE_CSV
    print("Welcome to the Stock Portfolio Performance Tracker.")
    print("Sample CSV prices are fictional examples for testing, not live quotes.")

    while True:
        print_menu(price_source)
        try:
            choice = input("Select an option (1-5): ").strip()
        except EOFError:
            print()
            return 0

        if choice == "1":
            try:
                prompt_add_holding(holdings)
            except EOFError:
                print()
                return 0
        elif choice == "2":
            compute_and_maybe_save(holdings, price_source, save=True)
        elif choice == "3":
            compute_and_maybe_save(holdings, price_source, save=True)
        elif choice == "4":
            price_source = change_price_source(price_source)
        elif choice == "5":
            print("Goodbye.")
            return 0
        else:
            print("Please enter a number from 1 to 5.")


if __name__ == "__main__":
    sys.exit(main())
