"""Evaluation-only benchmark on attributed public natural-language threads.

The first source adapter uses the Stack Exchange API because public contributions
have explicit CC BY-SA licensing and stable attribution URLs. Reddit ingestion is
intentionally not implemented: current Reddit Data API terms do not grant a general
right to use user content for ML/AI model training without rightsholder permission.

Downloaded text is never connected to the personal pilot EvidenceLedger. The module
writes a local JSONL corpus, groups all posts from one thread into one chronological
document to prevent train/test leakage, and runs the existing FVSC held-out test.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time as datetime_time, timezone
import hashlib
from html import unescape
from html.parser import HTMLParser
import json
from pathlib import Path
import statistics
import time
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .pilot_evaluation import HeldoutDocument, run_heldout_evaluation
from .pilot_runtime import _statement_rows, source_revision
from .text_parser_agnostic import (
    DEFAULT_STOPWORDS_RU_EN,
    ParseConfig,
    text_to_semantic_input,
)


CORPUS_SCHEMA = "fvsc-natural-language-jsonl-v1"
BENCHMARK_VERSION = "fvsc-public-thread-heldout-v1"
STACKEXCHANGE_API = "https://api.stackexchange.com/2.3"
MAX_PAGES = 20
MAX_RECORD_TEXT = 200_000


@dataclass(frozen=True)
class NaturalLanguageRecord:
    record_id: str
    thread_id: str
    record_type: str
    created_at: float
    text: str
    source_url: str
    site: str
    license: str
    author_name: str
    author_url: str | None
    modified_from_html: bool = True

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "NaturalLanguageRecord":
        if value.get("schema") != CORPUS_SCHEMA:
            raise ValueError("unsupported natural-language corpus schema")
        fields = {
            name: str(value.get(name, "")).strip()
            for name in (
                "record_id",
                "thread_id",
                "record_type",
                "text",
                "source_url",
                "site",
                "license",
                "author_name",
            )
        }
        if not all(fields.values()):
            raise ValueError("corpus record is missing a required string field")
        if fields["record_type"] not in {"question", "answer"}:
            raise ValueError("record_type must be question or answer")
        created_at = float(value.get("created_at"))
        if not created_at >= 0.0:
            raise ValueError("created_at must be non-negative")
        if len(fields["text"]) > MAX_RECORD_TEXT:
            raise ValueError("corpus record text exceeds the safety limit")
        author_url_raw = value.get("author_url")
        author_url = None if author_url_raw is None else str(author_url_raw).strip() or None
        return cls(
            record_id=fields["record_id"],
            thread_id=fields["thread_id"],
            record_type=fields["record_type"],
            created_at=created_at,
            text=fields["text"],
            source_url=fields["source_url"],
            site=fields["site"],
            license=fields["license"],
            author_name=fields["author_name"],
            author_url=author_url,
            modified_from_html=bool(value.get("modified_from_html", True)),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema": CORPUS_SCHEMA,
            "record_id": self.record_id,
            "thread_id": self.thread_id,
            "record_type": self.record_type,
            "created_at": self.created_at,
            "text": self.text,
            "source_url": self.source_url,
            "site": self.site,
            "license": self.license,
            "author_name": self.author_name,
            "author_url": self.author_url,
            "modified_from_html": self.modified_from_html,
            "usage_purpose": "evaluation_only_no_llm_training",
        }


class _ReadableHtml(HTMLParser):
    _BLOCKS = {
        "p", "div", "br", "li", "ul", "ol", "h1", "h2", "h3", "h4",
        "h5", "h6", "table", "tr", "blockquote",
    }
    _SKIP = {"pre", "code", "script", "style"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip_depth = 0
        self.quote_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.casefold()
        if tag in self._SKIP:
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        if tag == "blockquote":
            self.quote_depth += 1
            self.parts.append("\n[QUOTE] ")
        elif tag in self._BLOCKS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        if tag in self._SKIP:
            self.skip_depth = max(0, self.skip_depth - 1)
            return
        if self.skip_depth:
            return
        if tag == "blockquote":
            self.quote_depth = max(0, self.quote_depth - 1)
            self.parts.append("\n[/QUOTE]\n")
        elif tag in self._BLOCKS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.skip_depth:
            self.parts.append(data)

    def text(self) -> str:
        lines = [" ".join(unescape(line).split()) for line in "".join(self.parts).splitlines()]
        return "\n".join(line for line in lines if line).strip()


def html_to_text(value: str) -> str:
    parser = _ReadableHtml()
    parser.feed(str(value))
    parser.close()
    return parser.text()


def _license_for_timestamp(timestamp: float) -> str:
    before_2011 = datetime(2011, 4, 8, tzinfo=timezone.utc).timestamp()
    before_2018 = datetime(2018, 5, 2, tzinfo=timezone.utc).timestamp()
    if timestamp < before_2011:
        return "CC BY-SA 2.5"
    if timestamp < before_2018:
        return "CC BY-SA 3.0"
    return "CC BY-SA 4.0"


def _owner(item: Mapping[str, Any]) -> tuple[str, str | None]:
    owner = item.get("owner")
    if not isinstance(owner, Mapping):
        return "deleted Stack Exchange user", None
    name = html_to_text(str(owner.get("display_name", ""))) or "deleted Stack Exchange user"
    link = str(owner.get("link", "")).strip() or None
    return name, link


def _api_get(path: str, params: Mapping[str, Any], *, timeout: float = 30.0) -> dict[str, Any]:
    url = f"{STACKEXCHANGE_API}/{path.lstrip('/')}?{urlencode(params)}"
    request = Request(
        url,
        headers={
            "User-Agent": "FVSC-natural-language-benchmark/1.0 evaluation-only",
            "Accept": "application/json",
        },
    )
    with urlopen(request, timeout=timeout) as response:  # nosec: B310 - fixed HTTPS host
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("Stack Exchange API returned a non-object response")
    if payload.get("error_id"):
        raise RuntimeError(
            f"Stack Exchange API error {payload.get('error_id')}: "
            f"{payload.get('error_name')} {payload.get('error_message')}"
        )
    backoff = payload.get("backoff")
    if backoff is not None:
        time.sleep(max(0.0, float(backoff)))
    return payload


def _iso_timestamp(value: str | None, *, end_of_day: bool = False) -> int | None:
    if value is None:
        return None
    parsed = date.fromisoformat(value)
    clock = datetime_time.max if end_of_day else datetime_time.min
    return int(datetime.combine(parsed, clock, tzinfo=timezone.utc).timestamp())


def fetch_stackexchange_corpus(
    *,
    site: str,
    pages: int,
    output: Path,
    from_date: str | None = None,
    to_date: str | None = None,
    minimum_score: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    """Fetch an attributed local corpus without connecting it to personal state."""
    site_clean = str(site).strip()
    if not site_clean:
        raise ValueError("site must not be empty")
    if not 1 <= pages <= MAX_PAGES:
        raise ValueError(f"pages must be in [1, {MAX_PAGES}]")
    if not 1 <= page_size <= 100:
        raise ValueError("page_size must be in [1, 100]")

    question_items: list[dict[str, Any]] = []
    for page in range(1, pages + 1):
        params: dict[str, Any] = {
            "site": site_clean,
            "page": page,
            "pagesize": page_size,
            "order": "asc",
            "sort": "creation",
            "filter": "withbody",
        }
        start = _iso_timestamp(from_date)
        end = _iso_timestamp(to_date, end_of_day=True)
        if start is not None:
            params["fromdate"] = start
        if end is not None:
            params["todate"] = end
        payload = _api_get("questions", params)
        items = payload.get("items", [])
        if not isinstance(items, list):
            raise RuntimeError("questions response has invalid items")
        question_items.extend(
            item for item in items
            if isinstance(item, dict) and int(item.get("score", 0)) >= minimum_score
        )
        if not payload.get("has_more"):
            break

    question_items.sort(key=lambda item: (int(item.get("creation_date", 0)), int(item["question_id"])))
    question_by_id = {int(item["question_id"]): item for item in question_items}
    answer_items: list[dict[str, Any]] = []
    question_ids = sorted(question_by_id)
    for offset in range(0, len(question_ids), 100):
        batch = question_ids[offset : offset + 100]
        if not batch:
            continue
        answer_page = 1
        while True:
            payload = _api_get(
                f"questions/{';'.join(str(item) for item in batch)}/answers",
                {
                    "site": site_clean,
                    "page": answer_page,
                    "pagesize": 100,
                    "order": "asc",
                    "sort": "creation",
                    "filter": "withbody",
                },
            )
            items = payload.get("items", [])
            if not isinstance(items, list):
                raise RuntimeError("answers response has invalid items")
            answer_items.extend(item for item in items if isinstance(item, dict))
            if not payload.get("has_more"):
                break
            answer_page += 1

    records: list[NaturalLanguageRecord] = []
    for question in question_items:
        question_id = int(question["question_id"])
        created = float(question.get("creation_date", 0))
        title = html_to_text(str(question.get("title", "")))
        body = html_to_text(str(question.get("body", "")))
        text = f"{title}\n\n{body}".strip()
        if len(text) < 80:
            continue
        author_name, author_url = _owner(question)
        records.append(
            NaturalLanguageRecord(
                record_id=f"question:{question_id}",
                thread_id=str(question_id),
                record_type="question",
                created_at=created,
                text=text[:MAX_RECORD_TEXT],
                source_url=str(question.get("link", "")).strip(),
                site=site_clean,
                license=_license_for_timestamp(created),
                author_name=author_name,
                author_url=author_url,
            )
        )

    for answer in answer_items:
        question_id = int(answer.get("question_id", 0))
        question = question_by_id.get(question_id)
        if question is None:
            continue
        body = html_to_text(str(answer.get("body", "")))
        if len(body) < 80:
            continue
        created = float(answer.get("creation_date", 0))
        author_name, author_url = _owner(answer)
        question_url = str(question.get("link", "")).strip()
        answer_id = int(answer["answer_id"])
        records.append(
            NaturalLanguageRecord(
                record_id=f"answer:{answer_id}",
                thread_id=str(question_id),
                record_type="answer",
                created_at=created,
                text=body[:MAX_RECORD_TEXT],
                source_url=f"{question_url}#answer-{answer_id}",
                site=site_clean,
                license=_license_for_timestamp(created),
                author_name=author_name,
                author_url=author_url,
            )
        )

    records.sort(key=lambda item: (item.created_at, item.thread_id, item.record_id))
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record.to_mapping(), ensure_ascii=False, sort_keys=True))
            handle.write("\n")

    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    return {
        "schema": CORPUS_SCHEMA,
        "site": site_clean,
        "records": len(records),
        "threads": len({record.thread_id for record in records}),
        "questions": sum(record.record_type == "question" for record in records),
        "answers": sum(record.record_type == "answer" for record in records),
        "output": str(output),
        "sha256": digest,
        "quota_note": "respect API backoff and the current Stack Exchange API terms",
    }


def load_corpus(path: Path) -> tuple[NaturalLanguageRecord, ...]:
    records: list[NaturalLanguageRecord] = []
    seen: set[str] = set()
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
                record = NaturalLanguageRecord.from_mapping(value)
            except (json.JSONDecodeError, TypeError, ValueError) as exc:
                raise ValueError(f"invalid corpus record at line {line_number}: {exc}") from exc
            key = f"{record.site}\0{record.record_id}"
            if key in seen:
                raise ValueError(f"duplicate corpus record: {record.record_id}")
            seen.add(key)
            records.append(record)
    return tuple(sorted(records, key=lambda item: (item.created_at, item.thread_id, item.record_id)))


def _thread_documents(
    records: Sequence[NaturalLanguageRecord],
    *,
    max_threads: int | None,
) -> tuple[list[HeldoutDocument], dict[str, Any]]:
    grouped: dict[tuple[str, str], list[NaturalLanguageRecord]] = defaultdict(list)
    for record in records:
        grouped[(record.site, record.thread_id)].append(record)

    ordered_groups = sorted(
        grouped.items(),
        key=lambda item: (
            min(record.created_at for record in item[1]),
            item[0][0],
            item[0][1],
        ),
    )
    if max_threads is not None:
        ordered_groups = ordered_groups[:max_threads]

    config = ParseConfig(
        window=5,
        min_freq=2,
        max_concepts=300,
        min_token_len=2,
        stopwords=DEFAULT_STOPWORDS_RU_EN,
        keep_top_contains=10,
        weight_threshold=0.05,
    )
    documents: list[HeldoutDocument] = []
    skipped_short = 0
    skipped_unparseable = 0
    relation_count = 0
    text_lengths: list[int] = []
    quote_marked_threads = 0

    for (site, thread_id), thread_records in ordered_groups:
        ordered = sorted(
            thread_records,
            key=lambda item: (item.created_at, item.record_type != "question", item.record_id),
        )
        sections = []
        for record in ordered:
            label = "QUESTION" if record.record_type == "question" else "ANSWER"
            sections.append(f"[{label}]\n{record.text}")
        text = "\n\n".join(sections).strip()
        if len(text) < 200:
            skipped_short += 1
            continue
        semantic_input = text_to_semantic_input(text, config=config)
        relations = len(_statement_rows(semantic_input))
        if not semantic_input or relations == 0:
            skipped_unparseable += 1
            continue
        if "[QUOTE]" in text:
            quote_marked_threads += 1
        relation_count += relations
        text_lengths.append(len(text))
        documents.append(
            HeldoutDocument(
                source_id=f"{site}:thread:{thread_id}",
                observed_at=min(record.created_at for record in ordered),
                semantic_input=semantic_input,
                source_revision=source_revision(text),
            )
        )

    diagnostics = {
        "threads_seen": len(ordered_groups),
        "parseable_threads": len(documents),
        "skipped_short": skipped_short,
        "skipped_unparseable": skipped_unparseable,
        "parser_relations": relation_count,
        "quote_marked_threads": quote_marked_threads,
        "median_thread_characters": statistics.median(text_lengths) if text_lengths else 0,
    }
    return documents, diagnostics


def evaluate_corpus(
    input_path: Path,
    *,
    output_path: Path,
    train_fraction: float = 0.8,
    bootstrap_samples: int = 1000,
    max_threads: int | None = None,
) -> dict[str, Any]:
    records = load_corpus(input_path)
    documents, diagnostics = _thread_documents(records, max_threads=max_threads)
    evaluation = run_heldout_evaluation(
        documents,
        train_fraction=train_fraction,
        bootstrap_samples=bootstrap_samples,
    )
    license_counts = Counter(record.license for record in records)
    site_counts = Counter(record.site for record in records)
    attribution_complete = sum(bool(record.author_name and record.source_url) for record in records)
    report = {
        "benchmark": BENCHMARK_VERSION,
        "generated_at": time.time(),
        "corpus": {
            "schema": CORPUS_SCHEMA,
            "path": str(input_path),
            "sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
            "records": len(records),
            "threads": len({(record.site, record.thread_id) for record in records}),
            "sites": dict(sorted(site_counts.items())),
            "licenses": dict(sorted(license_counts.items())),
            "attribution_complete_rate": (
                attribution_complete / len(records) if records else 0.0
            ),
            "usage_purpose": "evaluation_only_no_llm_training",
            "raw_text_in_report": False,
        },
        "parser_diagnostics": diagnostics,
        "evaluation": evaluation,
        "interpretation_rules": [
            "public corpus results measure technical robustness, not personal usefulness",
            "all posts from one thread remain on one side of the chronological split",
            "parser-derived relations remain proxy labels and require manual audit",
            "no public corpus record is written to the personal EvidenceLedger",
            "source license and attribution metadata must be preserved with local corpus copies",
        ],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    return report


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    fetch = subparsers.add_parser("fetch-stackexchange")
    fetch.add_argument("--site", default="workplace")
    fetch.add_argument("--pages", type=int, default=3)
    fetch.add_argument("--page-size", type=int, default=100)
    fetch.add_argument("--minimum-score", type=int, default=1)
    fetch.add_argument("--from-date")
    fetch.add_argument("--to-date")
    fetch.add_argument("--output", type=Path, required=True)

    evaluate = subparsers.add_parser("evaluate")
    evaluate.add_argument("--input", type=Path, required=True)
    evaluate.add_argument("--output", type=Path, required=True)
    evaluate.add_argument("--train-fraction", type=float, default=0.8)
    evaluate.add_argument("--bootstrap-samples", type=int, default=1000)
    evaluate.add_argument("--max-threads", type=int)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "fetch-stackexchange":
        result = fetch_stackexchange_corpus(
            site=args.site,
            pages=args.pages,
            page_size=args.page_size,
            minimum_score=args.minimum_score,
            from_date=args.from_date,
            to_date=args.to_date,
            output=args.output,
        )
    else:
        result = evaluate_corpus(
            args.input,
            output_path=args.output,
            train_fraction=args.train_fraction,
            bootstrap_samples=args.bootstrap_samples,
            max_threads=args.max_threads,
        )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
