#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import yfinance as yf


DEFAULT_TICKERS = ["^N225", "^TOPX"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch daily market data for specified effective business dates."
    )
    parser.add_argument(
        "--manifest",
        required=True,
        help="Manifest JSON produced by build_daily_llm_inputs.py",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory to write market data files into.",
    )
    parser.add_argument(
        "--tickers",
        nargs="*",
        default=DEFAULT_TICKERS,
        help="Yahoo Finance tickers to fetch.",
    )
    return parser.parse_args()


def load_manifest_dates(path: Path) -> list[date]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [date.fromisoformat(item["market_effective_date_jst"]) for item in payload]


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def fetch_ticker_frame(ticker: str, start: date, end: date) -> pd.DataFrame:
    frame = yf.download(
        ticker,
        start=start.isoformat(),
        end=(end + timedelta(days=1)).isoformat(),
        interval="1d",
        auto_adjust=False,
        progress=False,
        threads=False,
    )
    if frame.empty:
        return frame
    frame = frame.reset_index()
    flattened: list[str] = []
    for col in frame.columns:
        if isinstance(col, tuple):
            first = str(col[0])
            flattened.append(first)
        else:
            flattened.append(str(col))
    frame.columns = flattened
    return frame


def build_rows(frame: pd.DataFrame, ticker: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    previous_close: float | None = None
    for _, raw in frame.iterrows():
        trade_date = pd.Timestamp(raw["Date"]).date().isoformat()
        open_price = float(raw["Open"])
        high_price = float(raw["High"])
        low_price = float(raw["Low"])
        close_price = float(raw["Close"])
        adj_close = float(raw["Adj Close"]) if "Adj Close" in frame.columns else close_price
        volume = int(raw["Volume"]) if not pd.isna(raw["Volume"]) else 0
        day_change = close_price - open_price
        day_change_pct = (day_change / open_price * 100.0) if open_price else None
        close_change = None
        close_change_pct = None
        if previous_close not in (None, 0):
            close_change = close_price - previous_close
            close_change_pct = close_change / previous_close * 100.0
        rows.append(
            {
                "ticker": ticker,
                "trade_date": trade_date,
                "open": round(open_price, 4),
                "high": round(high_price, 4),
                "low": round(low_price, 4),
                "close": round(close_price, 4),
                "adj_close": round(adj_close, 4),
                "volume": volume,
                "day_change": round(day_change, 4),
                "day_change_pct": round(day_change_pct, 6) if day_change_pct is not None else "",
                "prev_close_change": round(close_change, 4) if close_change is not None else "",
                "prev_close_change_pct": round(close_change_pct, 6) if close_change_pct is not None else "",
            }
        )
        previous_close = close_price
    return rows


def main() -> None:
    args = parse_args()
    manifest_dates = sorted(load_manifest_dates(Path(args.manifest)))
    if not manifest_dates:
        raise SystemExit("No dates found in manifest.")

    start = manifest_dates[0] - timedelta(days=7)
    end = manifest_dates[-1] + timedelta(days=7)

    all_rows: list[dict[str, Any]] = []
    requested_rows: list[dict[str, Any]] = []
    requested_dates = {d.isoformat() for d in manifest_dates}

    for ticker in args.tickers:
        frame = fetch_ticker_frame(ticker, start, end)
        rows = build_rows(frame, ticker)
        all_rows.extend(rows)
        requested_rows.extend([row for row in rows if row["trade_date"] in requested_dates])

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    write_csv(output_dir / "market_data_all.csv", all_rows)
    write_csv(output_dir / "market_data_requested_dates.csv", requested_rows)
    (output_dir / "fetch_report.json").write_text(
        json.dumps(
            {
                "tickers": args.tickers,
                "requested_dates": sorted(requested_dates),
                "history_fetch_start": start.isoformat(),
                "history_fetch_end": end.isoformat(),
                "all_row_count": len(all_rows),
                "requested_row_count": len(requested_rows),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
