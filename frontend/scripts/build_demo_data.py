from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_RANGE = "2025-06-22_2025-06-28"
OUTPUT_PATH = REPO_ROOT / "frontend" / "public" / "assets" / "data" / "demo-data.json"


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def parse_topic_group(row: dict[str, str], prefix: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for index in range(1, 6):
        name = row.get(f"{prefix}_{index}_name", "").strip()
        if not name:
            continue
        count = int(float(row.get(f"{prefix}_{index}_count", "0") or 0))
        ratio_key = f"{prefix}_{index}_ratio"
        ratio_value = row.get(ratio_key)
        ratio = float(ratio_value) if ratio_value not in (None, "") else 0.0
        items.append({"name": name, "count": count, "ratio": ratio})
    return items


def main() -> None:
    comparison_rows = {
        row["market_effective_date_jst"]: row
        for row in read_csv_rows(
            REPO_ROOT / "backend" / "data" / "daily_comparison" / DATA_RANGE / "daily_comparison.csv"
        )
    }
    manifest = json.loads(
        (REPO_ROOT / "backend" / "data" / "gemini_outputs" / DATA_RANGE / "manifest.json").read_text(
            encoding="utf-8"
        )
    )

    records = []
    for entry in manifest:
        date = entry["market_effective_date_jst"]
        summary_path = REPO_ROOT / entry["summary_path"]
        embedding_path = REPO_ROOT / "backend" / "data" / "gemini_outputs" / DATA_RANGE / date / "embedding.json"
        summary = summary_path.read_text(encoding="utf-8").strip()
        embedding_payload = json.loads(embedding_path.read_text(encoding="utf-8"))
        comparison = comparison_rows[date]
        sample_headlines = json.loads(comparison["sample_headlines_json"])

        records.append(
            {
                "marketEffectiveDateJst": date,
                "articleCount": int(comparison["article_count"]),
                "sampleHeadlines": sample_headlines,
                "summary": summary,
                "embedding": embedding_payload["values"],
                "embeddingVectorLength": embedding_payload["vector_length"],
                "topics": {
                    "brands": parse_topic_group(comparison, "brand"),
                    "genres": parse_topic_group(comparison, "genre"),
                    "countries": parse_topic_group(comparison, "country"),
                    "companies": parse_topic_group(comparison, "company"),
                },
                "market": {
                    "n225Close": float(comparison["N225_close"]) if comparison["N225_close"] else None,
                    "n225PrevCloseChangePct": float(comparison["N225_prev_close_change_pct"])
                    if comparison["N225_prev_close_change_pct"]
                    else None,
                    "topixProxyClose": float(comparison["1306_T_close"]) if comparison["1306_T_close"] else None,
                    "topixProxyPrevCloseChangePct": float(comparison["1306_T_prev_close_change_pct"])
                    if comparison["1306_T_prev_close_change_pct"]
                    else None,
                },
            }
        )

    payload = {
        "generatedAt": datetime.now().isoformat(),
        "sourceRange": DATA_RANGE,
        "records": records,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
