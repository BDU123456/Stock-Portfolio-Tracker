# Stock Portfolio Performance Tracker

A beginner-friendly Python 3 console application for tracking stock holdings. Enter ticker symbols, purchase prices, and share quantities. The program calculates invested capital, current market value, profit or loss, and percentage change for each holding and for the whole portfolio, then saves a summary CSV.

## Features

- Add multiple stock holdings stored in a Python dictionary
- Validate ticker, purchase price, and share quantity
- Ask before overwriting a duplicate ticker so existing data is not lost
- Load current prices from a local sample CSV by default (works offline)
- Optional live prices with `yfinance` if you install it
- Formatted console report that marks gains, losses, and missing prices
- Automatic export of the latest summary to `portfolio_summary.csv`
- Unit tests that do not require internet access

## Prerequisites

- Python 3.9 or newer
- No extra packages are required for the default (sample CSV) workflow

## How to run the program

From the project directory:

```bash
python portfolio.py
```

On some systems the command is `python3 portfolio.py`.

## How to enter stock holdings

1. Choose **1. Add a stock holding**.
2. Enter a ticker such as `AAPL` or `MSFT` (it cannot be empty).
3. Enter a purchase price per share (must be a positive number).
4. Enter the number of shares (must be a positive whole number).
5. Repeat option 1 for additional holdings.

If you enter a ticker that already exists, the program shows the current values and asks whether to update them. Answering no leaves the original holding unchanged.

Then choose **2. View portfolio performance** to see the report. Viewing also writes `portfolio_summary.csv`. You can choose **3** to save the same latest summary again.

## How the calculations work

For each holding:

1. Invested Amount = Purchase Price × Quantity
2. Current Market Value = Current Price × Quantity
3. Profit/Loss = Current Market Value − Invested Amount
4. Percentage Gain/Loss = (Profit/Loss ÷ Invested Amount) × 100

Portfolio totals:

- Total invested capital (priced holdings)
- Total current market value
- Total profit or loss
- Overall percentage = (Total profit/loss ÷ Total invested capital of priced holdings) × 100

Holdings without a current price are listed in the report but are **not** included in market-value or performance totals. The program reports how many holdings could not be priced and the invested capital of those holdings. A missing current price is never replaced with the purchase price.

Money values are rounded to two decimal places using banker's rounding (`decimal.Decimal`).

## Sample price dataset

`stock_prices.csv` is the default price source. It contains familiar tickers and **illustrative, fictional** prices for practice:

```text
Ticker,Current Price
AAPL,120.00
MSFT,220.00
GOOGL,150.00
AMZN,180.00
TSLA,250.00
NVDA,400.00
```

These are not live market quotes. The console report states that clearly.

If you point the program at a CSV that lists only ticker symbols (for example an S&P 500 constituents file), the program will explain that a Current Price column is required. Add prices to the file or use optional online retrieval.

## Optional online price retrieval

The default source is the sample CSV so the app works without internet.

To try live prices:

1. Install the optional library: `pip install yfinance`
2. Run the program and choose **4. Change price source**, then option 2

Network failures, unknown tickers, and missing quotes are reported as unavailable (`N/A`). They are excluded from performance totals.

## How to run unit tests

From the project directory:

```bash
python -m unittest test_portfolio.py -v
```

Tests cover invested amount, market value, profit, loss, percentage change, multi-stock totals, missing prices, empty and malformed CSV files, and invalid inputs. They use local sample data only.

## Example console output

```text
================================================================================
STOCK PORTFOLIO PERFORMANCE REPORT
================================================================================
Using sample prices from stock_prices.csv. These values are fictional examples, not live market prices.
--------------------------------------------------------------------------------
Ticker     Purchase      Qty      Current       Invested   Market Value    Profit/Loss     Change
--------------------------------------------------------------------------------
AAPL        $100.00       10      $120.00      $1,000.00      $1,200.00        +$200.00    +20.00%
MSFT        $200.00        5      $220.00      $1,000.00      $1,100.00        +$100.00    +10.00%
ZZZ          $40.00        3          N/A        $120.00            N/A             N/A        N/A
--------------------------------------------------------------------------------
Incomplete data: 1 holding(s) could not be priced (ZZZ).
Unpriced invested capital excluded from performance totals: $120.00
Total current market value: $2,300.00
Total profit/loss: +$300.00
Overall percentage gain/loss: +15.00%
================================================================================
Latest portfolio summary saved to portfolio_summary.csv.
```

## Generated CSV

Each save overwrites `portfolio_summary.csv` with the **latest** calculation (headers plus one row per holding). It is not a transaction history. Missing prices are stored as `N/A`.

`portfolio_summary.csv` is listed in `.gitignore` because it is generated on each run.

## Known limitations

- Holdings live in memory until you exit; the app does not reload previous holdings from disk.
- Duplicate tickers are treated as one position that you can replace, not as separate lots.
- Share quantity must be a whole number (no fractional shares).
- Sample CSV prices are fictional and become outdated on purpose.
- Live prices depend on `yfinance` and a working network; quotes can be delayed or unavailable.
- The latest summary file is overwritten; there is no built-in history log.
- This is an educational tracker, not investment advice or a brokerage tool.
