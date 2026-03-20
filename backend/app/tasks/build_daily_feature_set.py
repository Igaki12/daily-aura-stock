#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


TOP_K = 5


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build final daily feature set before embedding from merged daily comparison CSV."
    )
    parser.add_argument(
        "--comparison-csv",
        required=True,
        help="Path to daily_comparison.csv",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory to write final feature set files into.",
    )
    return parser.parse_args()


def load_rows(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def to_int(value: str) -> int:
    if value in ("", None):
        return 0
    return int(float(value))


def to_float(value: str) -> float:
    if value in ("", None):
        return 0.0
    return float(value)


def ratio(count: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return count / total


def build_embedding_text(row: dict[str, Any], article_count: int) -> str:
    lines: list[str] = []
    lines.append(f"market_effective_date_jst: {row['market_effective_date_jst']}")
    lines.append(f"article_count: {article_count}")

    genre_parts = []
    for i in range(1, TOP_K + 1):
        name = row.get(f"genre_{i}_name", "")
        count = to_int(row.get(f"genre_{i}_count", ""))
        if name:
            genre_parts.append(f"{name}({count})")
    if genre_parts:
        lines.append("top_genres: " + ", ".join(genre_parts))

    country_parts = []
    for i in range(1, TOP_K + 1):
        name = row.get(f"country_{i}_name", "")
        count = to_int(row.get(f"country_{i}_count", ""))
        if name:
            country_parts.append(f"{name}({count})")
    if country_parts:
        lines.append("top_countries: " + ", ".join(country_parts))

    company_parts = []
    for i in range(1, TOP_K + 1):
        name = row.get(f"company_{i}_name", "")
        count = to_int(row.get(f"company_{i}_count", ""))
        if name:
            company_parts.append(f"{name}({count})")
    if company_parts:
        lines.append("top_companies: " + ", ".join(company_parts))

    headlines = json.loads(row.get("sample_headlines_json", "[]"))
    if headlines:
        lines.append("sample_headlines: " + " / ".join(headlines[:10]))

    return "\n".join(lines)


def transform_row(row: dict[str, Any]) -> dict[str, Any]:
    article_count = to_int(row["article_count"])
    out: dict[str, Any] = {
        "market_effective_date_jst": row["market_effective_date_jst"],
        "article_count": article_count,
        "sample_headlines_json": row["sample_headlines_json"],
    }

    for i in range(1, TOP_K + 1):
        for prefix in ("brand", "genre", "country", "company"):
            name = row.get(f"{prefix}_{i}_name", "")
            count = to_int(row.get(f"{prefix}_{i}_count", ""))
            out[f"{prefix}_{i}_name"] = name
            out[f"{prefix}_{i}_count"] = count
            out[f"{prefix}_{i}_ratio"] = round(ratio(count, article_count), 6)

    market_numeric_fields = [
        "N225_open",
        "N225_high",
        "N225_low",
        "N225_close",
        "N225_adj_close",
        "N225_volume",
        "N225_day_change",
        "N225_day_change_pct",
        "N225_prev_close_change",
        "N225_prev_close_change_pct",
        "1306_T_open",
        "1306_T_high",
        "1306_T_low",
        "1306_T_close",
        "1306_T_adj_close",
        "1306_T_volume",
        "1306_T_day_change",
        "1306_T_day_change_pct",
        "1306_T_prev_close_change",
        "1306_T_prev_close_change_pct",
    ]
    for field in market_numeric_fields:
        if field.endswith("volume"):
            out[field] = to_int(row.get(field, ""))
        else:
            out[field] = round(to_float(row.get(field, "")), 6)

    out["embedding_input_text"] = build_embedding_text(row, article_count)
    return out


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    args = parse_args()
    rows = load_rows(Path(args.comparison_csv))
    feature_rows = [transform_row(row) for row in rows]

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    write_csv(output_dir / "daily_feature_set.csv", feature_rows)
    write_jsonl(output_dir / "daily_feature_set.jsonl", feature_rows)
    (output_dir / "feature_report.json").write_text(
        json.dumps(
            {
                "row_count": len(feature_rows),
                "top_k": TOP_K,
                "contains_embedding_input_text": True,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
