#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Join daily news summary and market data into one comparison CSV."
    )
    parser.add_argument(
        "--daily-summary-json",
        required=True,
        help="Path to daily_summary.json produced by extract_news_dataset.py",
    )
    parser.add_argument(
        "--market-csv",
        required=True,
        help="Path to market_data_requested_dates.csv produced by fetch_market_data.py",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory to write merged comparison dataset into.",
    )
    return parser.parse_args()


def load_daily_summary(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_market_rows(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def flatten_ranked_list(values: list[list[Any]], prefix: str, top_n: int = 5) -> dict[str, Any]:
    row: dict[str, Any] = {}
    for index in range(top_n):
        name_key = f"{prefix}_{index + 1}_name"
        count_key = f"{prefix}_{index + 1}_count"
        if index < len(values):
            row[name_key] = values[index][0]
            row[count_key] = values[index][1]
        else:
            row[name_key] = ""
            row[count_key] = ""
    return row


def pivot_market_rows(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_date: dict[str, dict[str, Any]] = {}
    for item in rows:
        trade_date = item["trade_date"]
        ticker = item["ticker"]
        if trade_date not in by_date:
            by_date[trade_date] = {}
        prefix = ticker.replace("^", "").replace(".", "_")
        for key, value in item.items():
            if key in {"ticker", "trade_date"}:
                continue
            by_date[trade_date][f"{prefix}_{key}"] = value
    return by_date


def build_rows(
    daily_summary: list[dict[str, Any]], market_map: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in daily_summary:
        market_date = item["market_effective_date_jst"]
        row: dict[str, Any] = {
            "market_effective_date_jst": market_date,
            "article_count": item["article_count"],
            "sample_headlines_json": json.dumps(
                item.get("sample_headlines", []), ensure_ascii=False
            ),
        }
        row.update(flatten_ranked_list(item.get("top_news_brands", []), "brand"))
        row.update(flatten_ranked_list(item.get("top_news_genres", []), "genre"))
        row.update(flatten_ranked_list(item.get("top_countries", []), "country"))
        row.update(flatten_ranked_list(item.get("top_companies", []), "company"))
        row.update(market_map.get(market_date, {}))
        rows.append(row)
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    fieldnames: list[str] = []
    seen = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)

    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    daily_summary = load_daily_summary(Path(args.daily_summary_json))
    market_rows = load_market_rows(Path(args.market_csv))
    market_map = pivot_market_rows(market_rows)
    merged_rows = build_rows(daily_summary, market_map)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "daily_comparison.csv", merged_rows)
    (output_dir / "comparison_report.json").write_text(
        json.dumps(
            {
                "daily_summary_count": len(daily_summary),
                "market_row_count": len(market_rows),
                "merged_row_count": len(merged_rows),
                "market_dates_with_prices": sorted(market_map.keys()),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
