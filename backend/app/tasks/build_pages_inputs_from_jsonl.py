#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.tasks.run_gemini_daily_pipeline import (
    DEFAULT_EMBED_MODEL,
    DEFAULT_OUTPUT_DIMENSIONALITY,
    DEFAULT_SUMMARY_MODEL,
    generate_embedding,
    generate_summary,
    load_api_key,
    write_json,
)


JST_CUTOFF_HOUR = 15
JST_CUTOFF_MINUTE = 30


@dataclass
class NormalizedRecord:
    news_item_id: str
    revision_id: int
    headline: str
    sub_headline: str
    content: str
    date_id: str
    this_revision_created: str
    market_effective_date_jst: str
    source_time_label: str
    subject_codes: list[str]
    named_entities: list[dict[str, Any]]
    source_path: str


def normalize_subject_codes(raw_codes: list[Any]) -> list[str]:
    values: list[str] = []
    for item in raw_codes:
        if isinstance(item, dict):
            subject = str(item.get("subject") or "").strip()
            subject_matter = str(item.get("subject_matter") or "").strip()
            if subject and subject_matter:
                values.append(f"{subject}/{subject_matter}")
            elif subject:
                values.append(subject)
        else:
            value = str(item).strip()
            if value:
                values.append(value)
    return values


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Pages Step 1-3 input files from extracted JSONL article data."
    )
    parser.add_argument(
        "--input-files",
        nargs="+",
        required=True,
        help="One or more JSONL files containing article records.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory to write market_effective_date_jst-based output files into.",
    )
    parser.add_argument(
        "--max-articles-per-day",
        type=int,
        default=120,
        help="Maximum number of articles to include in one Step 1 text file.",
    )
    parser.add_argument(
        "--max-body-chars",
        type=int,
        default=480,
        help="Maximum number of body characters per article block in Step 1 text.",
    )
    parser.add_argument(
        "--summary-model",
        default=DEFAULT_SUMMARY_MODEL,
        help="Gemini model used for daily summarization.",
    )
    parser.add_argument(
        "--embedding-model",
        default=DEFAULT_EMBED_MODEL,
        help="Gemini model used for embeddings.",
    )
    parser.add_argument(
        "--output-dimensionality",
        type=int,
        default=DEFAULT_OUTPUT_DIMENSIONALITY,
        help="Embedding output dimensionality.",
    )
    parser.add_argument(
        "--thinking-level",
        default="low",
        choices=["minimal", "low", "medium", "high"],
        help="Gemini thinking level for summarization.",
    )
    parser.add_argument(
        "--skip-gemini",
        action="store_true",
        help="Only create Step 1 news input files and metadata, skipping summary and embedding generation.",
    )
    return parser.parse_args()


def parse_jst_timestamp(raw: str) -> datetime:
    return datetime.strptime(raw, "%Y%m%dT%H%M%S%z")


def next_weekday(date_value: datetime) -> datetime:
    next_day = date_value + timedelta(days=1)
    while next_day.weekday() >= 5:
        next_day += timedelta(days=1)
    return next_day


def compute_market_effective_date_jst(raw_timestamp: str) -> tuple[str, bool]:
    dt = parse_jst_timestamp(raw_timestamp)
    cutoff = dt.replace(hour=JST_CUTOFF_HOUR, minute=JST_CUTOFF_MINUTE, second=0, microsecond=0)
    is_after_close = dt > cutoff
    if is_after_close:
        dt = next_weekday(dt)
    elif dt.weekday() >= 5:
        while dt.weekday() >= 5:
            dt += timedelta(days=1)
    return dt.date().isoformat(), is_after_close


def clip_text(value: str, max_chars: int) -> str:
    value = (value or "").strip().replace("\u3000", " ")
    value = " ".join(value.split())
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 1].rstrip() + "…"


def load_jsonl_records(paths: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        with path.open("r", encoding="utf-8") as file:
            for line in file:
                if line.strip():
                    rows.append(json.loads(line))
    return rows


def latest_usable_records(rows: list[dict[str, Any]]) -> list[NormalizedRecord]:
    latest_by_item: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row.get("status") != "Usable":
            continue
        if not (row.get("headline") or "").strip():
            continue
        if not (row.get("content") or "").strip():
            continue
        key = row.get("news_item_id", "")
        if not key:
            continue
        current = latest_by_item.get(key)
        if current is None or int(row.get("revision_id", 0)) > int(current.get("revision_id", 0)):
            latest_by_item[key] = row

    normalized: list[NormalizedRecord] = []
    for row in latest_by_item.values():
        market_date, _ = compute_market_effective_date_jst(row["this_revision_created"])
        created_at = parse_jst_timestamp(row["this_revision_created"])
        normalized.append(
            NormalizedRecord(
                news_item_id=row["news_item_id"],
                revision_id=int(row.get("revision_id", 0)),
                headline=(row.get("headline") or "").strip(),
                sub_headline=(row.get("sub_headline") or "").strip(),
                content=(row.get("content") or "").strip(),
                date_id=(row.get("date_id") or "").strip(),
                this_revision_created=row["this_revision_created"],
                market_effective_date_jst=market_date,
                source_time_label=created_at.strftime("%Y-%m-%d %H:%M:%S %z"),
                subject_codes=normalize_subject_codes(row.get("subject_codes") or []),
                named_entities=list(row.get("named_entities") or []),
                source_path=(row.get("source_tar_entry") or "").strip(),
            )
        )
    return sorted(
        normalized,
        key=lambda record: (
            record.market_effective_date_jst,
            record.this_revision_created,
            record.news_item_id,
        ),
    )


def top_named_entities(records: list[NormalizedRecord], limit: int = 10) -> list[tuple[str, int]]:
    counter: Counter[str] = Counter()
    for record in records:
        for entity in record.named_entities:
            if isinstance(entity, dict):
                name = str(entity.get("surface") or entity.get("name") or "").strip()
            else:
                name = str(entity).strip()
            if name:
                counter[name] += 1
    return counter.most_common(limit)


def top_subject_codes(records: list[NormalizedRecord], limit: int = 10) -> list[tuple[str, int]]:
    counter: Counter[str] = Counter()
    for record in records:
        for code in record.subject_codes:
            if code:
                counter[code] += 1
    return counter.most_common(limit)


def article_block(record: NormalizedRecord, max_body_chars: int) -> str:
    lines = [
        f"### {record.headline}",
        f"- 配信時刻JST: {record.source_time_label}",
        f"- NewsItemId: {record.news_item_id}",
        f"- RevisionId: {record.revision_id}",
    ]
    if record.sub_headline:
        lines.append(f"- サブ見出し: {record.sub_headline}")
    if record.subject_codes:
        lines.append(f"- SubjectCodes: {', '.join(record.subject_codes[:8])}")
    lines.append("- 本文:")
    lines.append(clip_text(record.content, max_body_chars))
    return "\n".join(lines)


def build_news_input_text(
    market_date: str,
    records: list[NormalizedRecord],
    max_articles_per_day: int,
    max_body_chars: int,
) -> tuple[str, dict[str, Any]]:
    selected = records[:max_articles_per_day]
    entities = top_named_entities(selected)
    subject_codes = top_subject_codes(selected)

    sections: list[str] = []
    sections.append("# Step 1 News Input")
    sections.append(f"- market_effective_date_jst: {market_date}")
    sections.append(f"- article_count_total: {len(records)}")
    sections.append(f"- article_count_included: {len(selected)}")
    sections.append("")
    sections.append("## 概要")
    sections.append("このテキストは、Pages デモの Step 1 にそのまま貼り付けられるように整形した1営業日分のニュース集合です。")
    sections.append("見出しだけでなく本文冒頭も含め、その日のニュース全体の空気感が読み取れるようにしています。")
    sections.append("")
    sections.append("### 主要見出しサンプル")
    for record in selected[:8]:
        sections.append(f"- {record.headline}")
    sections.append("")
    sections.append("### 上位 Named Entities")
    for name, count in entities:
        sections.append(f"- {name}: {count}")
    sections.append("")
    sections.append("### 上位 Subject Codes")
    for code, count in subject_codes:
        sections.append(f"- {code}: {count}")
    sections.append("")
    sections.append("## 記事一覧")
    for record in selected:
        sections.append("")
        sections.append(article_block(record, max_body_chars))

    metadata = {
        "market_effective_date_jst": market_date,
        "article_count_total": len(records),
        "article_count_included": len(selected),
        "max_articles_per_day": max_articles_per_day,
        "max_body_chars": max_body_chars,
        "top_named_entities": entities,
        "top_subject_codes": subject_codes,
        "sample_headlines": [record.headline for record in selected[:8]],
    }
    return "\n".join(sections).strip() + "\n", metadata


def compact_embedding_text(values: list[float]) -> str:
    return json.dumps(
        {
            "vector_length": len(values),
            "values": values,
        },
        ensure_ascii=False,
    )


def main() -> None:
    args = parse_args()
    input_paths = [Path(path) for path in args.input_files]
    rows = load_jsonl_records(input_paths)
    normalized_records = latest_usable_records(rows)

    grouped: dict[str, list[NormalizedRecord]] = defaultdict(list)
    for record in normalized_records:
        grouped[record.market_effective_date_jst].append(record)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    api_key = ""
    if not args.skip_gemini:
        api_key = load_api_key()

    manifest: list[dict[str, Any]] = []
    for market_date in sorted(grouped):
        records = grouped[market_date]
        news_input_text, metadata = build_news_input_text(
            market_date=market_date,
            records=records,
            max_articles_per_day=args.max_articles_per_day,
            max_body_chars=args.max_body_chars,
        )

        news_input_path = output_dir / f"{market_date}_news_input.txt"
        news_meta_path = output_dir / f"{market_date}_news_input.json"
        news_input_path.write_text(news_input_text, encoding="utf-8")
        write_json(news_meta_path, metadata)

        record_manifest: dict[str, Any] = {
            "market_effective_date_jst": market_date,
            "article_count_total": metadata["article_count_total"],
            "article_count_included": metadata["article_count_included"],
            "news_input_path": str(news_input_path),
            "news_input_meta_path": str(news_meta_path),
            "summary_path": "",
            "embedding_path": "",
            "embedding_compact_path": "",
            "summary_char_count": 0,
            "embedding_vector_length": 0,
        }

        if not args.skip_gemini:
            summary_text, summary_response = generate_summary(
                api_key=api_key,
                model=args.summary_model,
                thinking_level=args.thinking_level,
                daily_input_text=news_input_text,
            )
            summary_path = output_dir / f"{market_date}_summary.txt"
            summary_response_path = output_dir / f"{market_date}_summary_response.json"
            summary_path.write_text(summary_text, encoding="utf-8")
            write_json(summary_response_path, summary_response)

            vector, embedding_response = generate_embedding(
                api_key=api_key,
                model=args.embedding_model,
                text=summary_text,
                output_dimensionality=args.output_dimensionality,
            )
            embedding_path = output_dir / f"{market_date}_embedding.json"
            embedding_compact_path = output_dir / f"{market_date}_embedding.txt"
            embedding_response_path = output_dir / f"{market_date}_embedding_response.json"
            write_json(
                embedding_path,
                {
                    "market_effective_date_jst": market_date,
                    "model": args.embedding_model,
                    "output_dimensionality": args.output_dimensionality,
                    "vector_length": len(vector),
                    "values": vector,
                },
            )
            embedding_compact_path.write_text(compact_embedding_text(vector), encoding="utf-8")
            write_json(embedding_response_path, embedding_response)

            record_manifest.update(
                {
                    "summary_path": str(summary_path),
                    "summary_response_path": str(summary_response_path),
                    "embedding_path": str(embedding_path),
                    "embedding_compact_path": str(embedding_compact_path),
                    "embedding_response_path": str(embedding_response_path),
                    "summary_char_count": len(summary_text),
                    "embedding_vector_length": len(vector),
                    "summary_model": args.summary_model,
                    "embedding_model": args.embedding_model,
                    "output_dimensionality": args.output_dimensionality,
                }
            )
            time.sleep(1.0)

        manifest.append(record_manifest)

    write_json(output_dir / "manifest.json", manifest)


if __name__ == "__main__":
    main()
