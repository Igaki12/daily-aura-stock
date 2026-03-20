#!/usr/bin/env python3
from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
import time
from pathlib import Path
from typing import Any
from urllib import error, request


DEFAULT_SUMMARY_MODEL = "gemini-3-flash-preview"
DEFAULT_EMBED_MODEL = "gemini-embedding-001"
DEFAULT_OUTPUT_DIMENSIONALITY = 3072


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run daily news summarization and embedding with Gemini."
    )
    parser.add_argument(
        "--input-dir",
        required=True,
        help="Directory containing daily LLM input .txt files.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory to write Gemini outputs into.",
    )
    parser.add_argument(
        "--summary-model",
        default=DEFAULT_SUMMARY_MODEL,
        help="Gemini model used for daily summarization.",
    )
    parser.add_argument(
        "--embedding-model",
        default=DEFAULT_EMBED_MODEL,
        help="Gemini embedding model used for vector generation.",
    )
    parser.add_argument(
        "--output-dimensionality",
        type=int,
        default=DEFAULT_OUTPUT_DIMENSIONALITY,
        help="Embedding output dimensionality.",
    )
    parser.add_argument(
        "--skip-embedding",
        action="store_true",
        help="Only generate summaries and skip embedding generation.",
    )
    parser.add_argument(
        "--thinking-level",
        default="low",
        choices=["minimal", "low", "medium", "high"],
        help="Gemini thinking level for summarization.",
    )
    return parser.parse_args()


def load_api_key() -> str:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if api_key:
        return api_key
    if not sys.stdin.isatty():
        raise SystemExit("GEMINI_API_KEY is not set and no TTY is available for secret input.")
    api_key = getpass.getpass("Enter GEMINI_API_KEY: ").strip()
    if not api_key:
        raise SystemExit("Empty API key.")
    return api_key


def call_gemini_api(
    api_key: str,
    model: str,
    method: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:{method}"
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini API HTTP {exc.code}: {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Gemini API network error: {exc}") from exc


def build_summary_prompt(daily_input_text: str) -> str:
    return (
        "あなたは日本語ニュース全体の流れを整理する分析アシスタントです。\n"
        "以下は、ある1営業日に対応づけられたニュース記事群の前処理済みテキストです。\n"
        "記事の重複や速報の偏りを踏まえつつ、その日のニュース全体の空気感を、後段で意味類似検索しやすい文章として要約してください。\n\n"
        "出力要件:\n"
        "1. 日本語で出力すること\n"
        "2. 箇条書きではなく、自然な説明文中心でまとめること\n"
        "3. その日の全体傾向、主要トピック、トピックの比重、社会的・経済的インパクト、マーケット上の注目点を含めること\n"
        "4. 地震速報など件数の多い定型速報が多い場合は、その偏りをそのまま誇張せず、ニュース全体の中での位置づけとして扱うこと\n"
        "5. 400〜800文字程度を目安にすること\n"
        "6. 最終的な文章は後で embedding に使うため、具体性を保ちつつ冗長にしすぎないこと\n\n"
        "入力テキスト:\n"
        f"{daily_input_text}"
    )


def extract_summary_text(response: dict[str, Any]) -> str:
    candidates = response.get("candidates", [])
    parts: list[str] = []
    for candidate in candidates:
        content = candidate.get("content", {})
        for part in content.get("parts", []):
            text = part.get("text", "")
            if text:
                parts.append(text)
    summary = "\n".join(parts).strip()
    if not summary:
        raise RuntimeError(f"Gemini summary response did not contain text: {response}")
    return summary


def generate_summary(
    api_key: str,
    model: str,
    thinking_level: str,
    daily_input_text: str,
) -> tuple[str, dict[str, Any]]:
    prompt = build_summary_prompt(daily_input_text)
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "thinkingConfig": {
                "thinkingLevel": thinking_level,
            }
        },
    }
    response = call_gemini_api(api_key, model, "generateContent", payload)
    return extract_summary_text(response), response


def generate_embedding(
    api_key: str,
    model: str,
    text: str,
    output_dimensionality: int,
) -> tuple[list[float], dict[str, Any]]:
    payload = {
        "content": {"parts": [{"text": text}]},
        "taskType": "SEMANTIC_SIMILARITY",
        "output_dimensionality": output_dimensionality,
    }
    response = call_gemini_api(api_key, model, "embedContent", payload)
    values: list[float] = []

    # Gemini embedContent may return either:
    # - {"embedding": {"values": [...]}} for a single input
    # - {"embeddings": [{"values": [...]}]} for multiple inputs
    embedding_obj = response.get("embedding")
    if isinstance(embedding_obj, dict):
        values = embedding_obj.get("values", []) or []

    if not values:
        embeddings = response.get("embeddings", [])
        if embeddings:
            values = embeddings[0].get("values", []) or []

    if not values:
        raise RuntimeError(f"Gemini embedding response did not contain values: {response}")
    return values, response


def iter_input_files(input_dir: Path) -> list[Path]:
    return sorted(
        path for path in input_dir.glob("*.txt") if path.name[:4].isdigit()
    )


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    args = parse_args()
    api_key = load_api_key()
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest: list[dict[str, Any]] = []
    for input_path in iter_input_files(input_dir):
        market_date = input_path.stem
        daily_input_text = input_path.read_text(encoding="utf-8")

        summary_text, summary_response = generate_summary(
            api_key=api_key,
            model=args.summary_model,
            thinking_level=args.thinking_level,
            daily_input_text=daily_input_text,
        )

        day_dir = output_dir / market_date
        day_dir.mkdir(parents=True, exist_ok=True)
        (day_dir / "summary.txt").write_text(summary_text, encoding="utf-8")
        write_json(day_dir / "summary_response.json", summary_response)

        record: dict[str, Any] = {
            "market_effective_date_jst": market_date,
            "input_path": str(input_path),
            "summary_path": str(day_dir / "summary.txt"),
            "summary_model": args.summary_model,
            "embedding_model": "" if args.skip_embedding else args.embedding_model,
            "output_dimensionality": 0 if args.skip_embedding else args.output_dimensionality,
            "summary_char_count": len(summary_text),
            "embedding_vector_length": 0,
        }

        if not args.skip_embedding:
            vector, embedding_response = generate_embedding(
                api_key=api_key,
                model=args.embedding_model,
                text=summary_text,
                output_dimensionality=args.output_dimensionality,
            )
            write_json(
                day_dir / "embedding.json",
                {
                    "market_effective_date_jst": market_date,
                    "model": args.embedding_model,
                    "output_dimensionality": args.output_dimensionality,
                    "vector_length": len(vector),
                    "values": vector,
                },
            )
            write_json(day_dir / "embedding_response.json", embedding_response)
            record["embedding_vector_length"] = len(vector)

        manifest.append(record)
        time.sleep(1.0)

    write_json(output_dir / "manifest.json", manifest)


if __name__ == "__main__":
    main()
