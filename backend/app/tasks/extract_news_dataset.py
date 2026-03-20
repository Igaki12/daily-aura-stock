#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET


JST = timezone(timedelta(hours=9))
MARKET_CLOSE = time(15, 30)


@dataclass
class RawRecord:
    provider_id: str
    date_id: str
    news_item_id: str
    revision_id: int
    revision_update: str
    public_identifier: str
    transmission_id: str
    sent_at: str
    first_created: str
    this_revision_created: str
    source_timestamp_jst: str
    calendar_date_jst: str
    market_effective_date_jst: str
    is_after_close: bool
    status: str
    instruction: str
    has_news_component: bool
    news_service: list[str]
    news_brand: str
    headline: str
    subheadline: str
    keyword_line: str
    body_text: str
    body_paragraph_count: int
    subject_codes: list[dict[str, str]]
    area_codes: list[dict[str, str]]
    corporations: list[dict[str, str]]
    news_genres: list[dict[str, str]]
    group_id: str
    associated_with: list[dict[str, str]]
    raw_xml_path: str

    def to_row(self) -> dict[str, Any]:
        row = self.__dict__.copy()
        row["news_service"] = json.dumps(self.news_service, ensure_ascii=False)
        row["subject_codes"] = json.dumps(self.subject_codes, ensure_ascii=False)
        row["area_codes"] = json.dumps(self.area_codes, ensure_ascii=False)
        row["corporations"] = json.dumps(self.corporations, ensure_ascii=False)
        row["news_genres"] = json.dumps(self.news_genres, ensure_ascii=False)
        row["associated_with"] = json.dumps(self.associated_with, ensure_ascii=False)
        row["is_after_close"] = int(self.is_after_close)
        return row


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract NewsPack NewsML into analysis-friendly CSV/JSON."
    )
    parser.add_argument(
        "--input-root",
        default="CO",
        help="Root directory containing dated NewsML XML files.",
    )
    parser.add_argument(
        "--start-date",
        required=True,
        help="Start date in YYYY-MM-DD.",
    )
    parser.add_argument(
        "--end-date",
        required=True,
        help="End date in YYYY-MM-DD.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory to write extracted files into.",
    )
    return parser.parse_args()


def daterange(start: date, end: date) -> list[date]:
    days: list[date] = []
    current = start
    while current <= end:
        days.append(current)
        current += timedelta(days=1)
    return days


def parse_jst_timestamp(value: str) -> datetime | None:
    if not value:
        return None
    return datetime.strptime(value, "%Y%m%dT%H%M%S%z").astimezone(JST)


def is_business_day(day: date) -> bool:
    return day.weekday() < 5


def next_business_day(day: date) -> date:
    current = day
    while not is_business_day(current):
        current += timedelta(days=1)
    return current


def to_market_effective_date(source_dt: datetime) -> tuple[date, bool]:
    day = source_dt.date()
    after_close = source_dt.timetz().replace(tzinfo=None) > MARKET_CLOSE
    if not is_business_day(day):
        return next_business_day(day), after_close
    if after_close:
        return next_business_day(day + timedelta(days=1)), True
    return day, False


def find_text(node: ET.Element | None, path: str) -> str:
    if node is None:
        return ""
    target = node.find(path)
    if target is None or target.text is None:
        return ""
    return target.text.strip()


def attr(node: ET.Element | None, name: str) -> str:
    if node is None:
        return ""
    return (node.attrib.get(name) or "").strip()


def parse_subject_codes(component: ET.Element | None) -> list[dict[str, str]]:
    if component is None:
        return []
    output: list[dict[str, str]] = []
    for subject_code in component.findall("./DescriptiveMetadata/SubjectCode"):
        output.append(
            {
                "subject": attr(subject_code.find("Subject"), "FormalName"),
                "subject_matter": attr(subject_code.find("SubjectMatter"), "FormalName"),
                "subject_detail": attr(subject_code.find("SubjectDetail"), "FormalName"),
            }
        )
    return output


def parse_area_codes(component: ET.Element | None) -> list[dict[str, str]]:
    if component is None:
        return []
    output: list[dict[str, str]] = []
    for metadata in component.findall("./Metadata"):
        metadata_type = attr(metadata.find("MetadataType"), "FormalName")
        if metadata_type != "NskAreaInformation":
            continue
        for prop in metadata.findall("./Property"):
            if attr(prop, "FormalName") != "NskRelevantArea":
                continue
            output.append(
                {
                    "country": attr(
                        prop.find("./Property[@FormalName='NskCountry']"), "Value"
                    ),
                    "jpn_area_code": attr(
                        prop.find("./Property[@FormalName='NskJpnAreaCode']"), "Value"
                    ),
                }
            )
    return output


def parse_corporations(component: ET.Element | None) -> list[dict[str, str]]:
    if component is None:
        return []
    output: list[dict[str, str]] = []
    for metadata in component.findall("./Metadata"):
        metadata_type = attr(metadata.find("MetadataType"), "FormalName")
        if metadata_type != "KyodoCorporationInfo":
            continue
        for corp in metadata.findall(".//Property[@FormalName='Corporation']"):
            output.append(
                {
                    "stock_code": attr(corp.find("./Property[@FormalName='StockCode']"), "Value"),
                    "market": attr(corp.find("./Property[@FormalName='Market']"), "Value"),
                    "name": attr(corp.find("./Property[@FormalName='Name']"), "Value"),
                }
            )
    return output


def parse_brand_and_genres(component: ET.Element | None) -> tuple[str, list[dict[str, str]]]:
    if component is None:
        return "", []
    news_brand = ""
    news_genres: list[dict[str, str]] = []
    for metadata in component.findall("./Metadata"):
        metadata_type = attr(metadata.find("MetadataType"), "FormalName")
        if metadata_type != "CorporationInfo/NewsBrandInfo/NewsGenreInfo":
            continue
        news_brand = attr(
            metadata.find(".//Property[@FormalName='NewsBrand']"), "Value"
        )
        genre_info = metadata.find("./Property[@FormalName='NewsGenreInfo']")
        if genre_info is None:
            continue
        for major in genre_info.findall("./Property"):
            genre = major.find("./Property[@FormalName='NewsGenre']")
            if genre is None:
                continue
            news_genres.append(
                {
                    "major": attr(major, "FormalName"),
                    "minor": attr(genre, "Value"),
                }
            )
    return news_brand, news_genres


def parse_group_id(component: ET.Element | None) -> str:
    if component is None:
        return ""
    for metadata in component.findall("./Metadata"):
        metadata_type = attr(metadata.find("MetadataType"), "FormalName")
        if metadata_type == "GroupId":
            return attr(metadata.find("./Property[@FormalName='GroupId']"), "Value")
    return ""


def parse_associated_with(news_item: ET.Element | None) -> list[dict[str, str]]:
    if news_item is None:
        return []
    output: list[dict[str, str]] = []
    for assoc in news_item.findall("./NewsManagement/AssociatedWith"):
        output.append(
            {
                "news_item": attr(assoc, "NewsItem"),
                "comment": find_text(assoc, "Comment"),
                "euid": attr(assoc, "Euid"),
            }
        )
    return output


def parse_body(component: ET.Element | None) -> tuple[str, int]:
    if component is None:
        return "", 0
    paragraphs = [
        (p.text or "").strip()
        for p in component.findall("./ContentItem/DataContent/newstext/body/news.content/p")
        if (p.text or "").strip()
    ]
    return "\n".join(paragraphs), len(paragraphs)


def parse_news_services(root: ET.Element) -> list[str]:
    services: list[str] = []
    for service in root.findall("./NewsEnvelope/NewsService"):
        formal_name = attr(service, "FormalName")
        if formal_name:
            services.append(formal_name)
    return services


def parse_record(xml_path: Path) -> RawRecord:
    root = ET.parse(xml_path).getroot()
    news_item = root.find("./NewsItem")
    component = news_item.find("./NewsComponent") if news_item is not None else None
    revision = news_item.find("./Identification/NewsIdentifier/RevisionId") if news_item is not None else None

    sent_at = find_text(root, "./NewsEnvelope/DateAndTime")
    this_revision_created = find_text(news_item, "./NewsManagement/ThisRevisionCreated")
    source_dt = parse_jst_timestamp(this_revision_created) or parse_jst_timestamp(sent_at)
    if source_dt is None:
        raise ValueError(f"Missing timestamp in {xml_path}")
    market_effective_date, after_close = to_market_effective_date(source_dt)

    body_text, body_paragraph_count = parse_body(component)
    news_brand, news_genres = parse_brand_and_genres(component)

    return RawRecord(
        provider_id=find_text(news_item, "./Identification/NewsIdentifier/ProviderId"),
        date_id=find_text(news_item, "./Identification/NewsIdentifier/DateId"),
        news_item_id=find_text(news_item, "./Identification/NewsIdentifier/NewsItemId"),
        revision_id=int((revision.text or "0").strip()) if revision is not None and revision.text else 0,
        revision_update=attr(revision, "Update"),
        public_identifier=find_text(news_item, "./Identification/NewsIdentifier/PublicIdentifier"),
        transmission_id=find_text(root, "./NewsEnvelope/TransmissionId"),
        sent_at=sent_at,
        first_created=find_text(news_item, "./NewsManagement/FirstCreated"),
        this_revision_created=this_revision_created,
        source_timestamp_jst=source_dt.isoformat(),
        calendar_date_jst=source_dt.date().isoformat(),
        market_effective_date_jst=market_effective_date.isoformat(),
        is_after_close=after_close,
        status=attr(news_item.find("./NewsManagement/Status") if news_item is not None else None, "FormalName"),
        instruction=attr(news_item.find("./NewsManagement/Instruction") if news_item is not None else None, "FormalName"),
        has_news_component=component is not None,
        news_service=parse_news_services(root),
        news_brand=news_brand,
        headline=find_text(component, "./NewsLines/HeadLine"),
        subheadline=find_text(component, "./NewsLines/SubHeadLine"),
        keyword_line=find_text(component, "./NewsLines/KeywordLine"),
        body_text=body_text,
        body_paragraph_count=body_paragraph_count,
        subject_codes=parse_subject_codes(component),
        area_codes=parse_area_codes(component),
        corporations=parse_corporations(component),
        news_genres=news_genres,
        group_id=parse_group_id(component),
        associated_with=parse_associated_with(news_item),
        raw_xml_path=str(xml_path),
    )


def normalize_text_for_analysis(record: RawRecord) -> str:
    parts: list[str] = []
    if record.headline:
        parts.append(record.headline)
    if record.subheadline:
        parts.append(record.subheadline)
    if record.keyword_line:
        parts.append(record.keyword_line)
    if record.news_brand or record.news_genres:
        genre_text = ", ".join(
            f"{item['major']}:{item['minor']}" for item in record.news_genres if item["minor"]
        )
        parts.append(" / ".join(filter(None, [record.news_brand, genre_text])))
    if record.subject_codes:
        subject_text = ", ".join(
            item["subject"] for item in record.subject_codes if item["subject"]
        )
        if subject_text:
            parts.append(subject_text)
    if record.body_text:
        parts.append(record.body_text)
    return "\n".join(parts)


def resolve_current_records(records: list[RawRecord]) -> list[dict[str, Any]]:
    grouped: dict[str, list[RawRecord]] = defaultdict(list)
    for record in records:
        grouped[record.news_item_id].append(record)

    current_rows: list[dict[str, Any]] = []
    for news_item_id, versions in grouped.items():
        versions.sort(
            key=lambda item: (
                item.revision_id,
                item.source_timestamp_jst,
                item.raw_xml_path,
            )
        )

        state: RawRecord | None = None
        active = False
        for version in versions:
            if version.revision_update == "A" and version.status == "Canceled":
                state = version
                active = False
                continue
            if version.revision_update == "A" and version.status == "Usable" and not version.has_news_component:
                if state is not None:
                    state = RawRecord(
                        **{
                            **state.__dict__,
                            "associated_with": version.associated_with,
                            "source_timestamp_jst": version.source_timestamp_jst,
                            "calendar_date_jst": version.calendar_date_jst,
                            "market_effective_date_jst": version.market_effective_date_jst,
                            "is_after_close": version.is_after_close,
                            "sent_at": version.sent_at,
                            "this_revision_created": version.this_revision_created,
                            "revision_id": version.revision_id,
                            "revision_update": version.revision_update,
                            "status": version.status,
                            "instruction": version.instruction,
                            "raw_xml_path": version.raw_xml_path,
                        }
                    )
                    active = True
                continue
            state = version
            active = version.status == "Usable"

        if state is None or not active:
            continue

        row = state.to_row()
        row["analysis_text"] = normalize_text_for_analysis(state)
        current_rows.append(row)

    current_rows.sort(key=lambda row: (row["market_effective_date_jst"], row["news_item_id"]))
    return current_rows


def build_daily_summary(current_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in current_rows:
        grouped[row["market_effective_date_jst"]].append(row)

    output: list[dict[str, Any]] = []
    for market_date in sorted(grouped):
        rows = grouped[market_date]
        brand_counter = Counter()
        genre_counter = Counter()
        country_counter = Counter()
        company_counter = Counter()

        for row in rows:
            if row["news_brand"]:
                brand_counter[row["news_brand"]] += 1
            for item in json.loads(row["news_genres"]):
                if item.get("minor"):
                    genre_counter[item["minor"]] += 1
            for item in json.loads(row["area_codes"]):
                if item.get("country"):
                    country_counter[item["country"]] += 1
            for item in json.loads(row["corporations"]):
                if item.get("name"):
                    company_counter[item["name"]] += 1

        output.append(
            {
                "market_effective_date_jst": market_date,
                "article_count": len(rows),
                "top_news_brands": brand_counter.most_common(10),
                "top_news_genres": genre_counter.most_common(10),
                "top_countries": country_counter.most_common(10),
                "top_companies": company_counter.most_common(10),
                "sample_headlines": [row["headline"] for row in rows[:10] if row["headline"]],
            }
        )
    return output


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    args = parse_args()
    start = date.fromisoformat(args.start_date)
    end = date.fromisoformat(args.end_date)

    xml_paths: list[Path] = []
    input_root = Path(args.input_root)
    for day in daterange(start, end):
        xml_paths.extend(sorted((input_root / day.strftime("%Y/%m/%d")).glob("*.xml")))

    records = [parse_record(path) for path in xml_paths]
    raw_rows = [record.to_row() for record in records]
    current_rows = resolve_current_records(records)
    daily_summary = build_daily_summary(current_rows)

    output_dir = Path(args.output_dir)
    write_csv(output_dir / "news_raw.csv", raw_rows)
    write_csv(output_dir / "news_current.csv", current_rows)
    write_json(output_dir / "daily_summary.json", daily_summary)
    write_json(
        output_dir / "extract_report.json",
        {
            "input_root": str(input_root),
            "start_date": args.start_date,
            "end_date": args.end_date,
            "raw_file_count": len(xml_paths),
            "raw_record_count": len(raw_rows),
            "current_record_count": len(current_rows),
            "daily_summary_count": len(daily_summary),
            "market_close_jst": MARKET_CLOSE.strftime("%H:%M:%S"),
            "business_day_rule": "weekday_only",
        },
    )


if __name__ == "__main__":
    main()
