#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import unicodedata
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from io import StringIO
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlencode, urljoin, urlparse, urlunparse
from urllib.request import urlopen


BACKEND_DIR = Path(__file__).resolve().parents[1]

DEFAULT_COMPETITIONS_URL = "https://fechida.cl/campeonatos-natacion/"
DEFAULT_CALENDAR_URL = "https://fechida.cl/calendario-por-mes/"
FECHIDA_BASE_URL = "https://fechida.cl/"
RESULT_KEYWORDS = ("resultado", "resultados", "results", "meet results")
MASTER_PATTERN = re.compile(r"\b(?:pre[-\s]?master|master|masters)\b", re.IGNORECASE)


@dataclass
class Competition:
    competition_id: int
    title: str
    start_date: str | None = None
    end_date: str | None = None
    place: str | None = None
    info_url: str | None = None


@dataclass
class Document:
    source_url: str
    title: str
    extension: str


@dataclass
class ManifestEntry:
    source_url: str
    pdf: str
    out_dir: str
    competition_id: int | None
    default_source_id: int
    source_system: str = "fechida"
    competition_scope: str = "fechida_master"
    fechida_competition_id: int | None = None
    competition_title: str | None = None


@dataclass
class CalendarEvent:
    date: str
    name: str
    discipline: str
    source_url: str
    gid: str | None = None
    sheet_name: str | None = None


class AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.anchors: list[dict[str, str]] = []
        self._current_href: str | None = None
        self._current_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        for name, value in attrs:
            if name.lower() == "href" and value:
                self._current_href = value
                self._current_text = []
                return

    def handle_data(self, data: str) -> None:
        if self._current_href is not None:
            self._current_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or self._current_href is None:
            return
        self.anchors.append({"href": self._current_href, "text": normalize_spaces("".join(self._current_text))})
        self._current_href = None
        self._current_text = []


def read_url_text(url: str, timeout_seconds: int) -> str:
    with urlopen(url, timeout=timeout_seconds) as response:
        encoding = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(encoding, errors="replace")


def normalize_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def strip_tags(value: str) -> str:
    return normalize_spaces(re.sub(r"<[^>]+>", " ", value))


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_name).strip("-").lower()
    return slug or "documento"


def info_url_for_id(competition_id: int) -> str:
    return f"https://fechida.cl/campeonato-info/?id={competition_id}"


def parse_competitions_table(html: str, base_url: str = DEFAULT_COMPETITIONS_URL) -> list[Competition]:
    row_pattern = re.compile(
        r'<tr>\s*<td>\s*<a\s+href="([^"]*campeonato-info\?id=(\d+)[^"]*)">(.*?)</a>\s*</td>'
        r"\s*<td>(.*?)</td>\s*<td>(.*?)</td>",
        re.IGNORECASE | re.DOTALL,
    )
    competitions: list[Competition] = []
    seen: set[int] = set()
    for match in row_pattern.finditer(html):
        competition_id = int(match.group(2))
        if competition_id in seen:
            continue
        seen.add(competition_id)
        dates = [strip_tags(part) for part in re.split(r"<br\s*/?>", match.group(4), flags=re.IGNORECASE)]
        dates = [date for date in dates if date]
        competitions.append(
            Competition(
                competition_id=competition_id,
                title=strip_tags(match.group(3)),
                start_date=dates[0] if dates else None,
                end_date=dates[1] if len(dates) > 1 else (dates[0] if dates else None),
                place=strip_tags(match.group(5)),
                info_url=urljoin(base_url, match.group(1)),
            )
        )
    return competitions


def is_master_competition(competition: Competition) -> bool:
    return bool(MASTER_PATTERN.search(competition.title))


def extract_info_title(html: str) -> str | None:
    for pattern in (
        r"<h[1-4][^>]*>\s*(?!Campeonato Info\b)(.*?)</h[1-4]>",
        r"Campeonato Info\s*</[^>]+>\s*<[^>]+>\s*([^<]+)",
    ):
        match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        if match:
            title = strip_tags(match.group(1))
            if title:
                return title
    plain = strip_tags(html)
    match = re.search(r"Campeonato Info\s+(.+?)\s+Lugar:", plain, re.IGNORECASE)
    return normalize_spaces(match.group(1)) if match else None


def extract_info_dates(html: str) -> tuple[str | None, str | None]:
    plain = strip_tags(html)
    dates = re.findall(r"\b20\d{2}-\d{2}-\d{2}\b", plain)
    if not dates:
        return None, None
    return dates[0], dates[1] if len(dates) > 1 else dates[0]


def parse_competition_info(html: str, competition_id: int, url: str) -> Competition:
    start_date, end_date = extract_info_dates(html)
    return Competition(
        competition_id=competition_id,
        title=extract_info_title(html) or f"fechida-{competition_id}",
        start_date=start_date,
        end_date=end_date,
        info_url=url,
    )


def document_extension(url: str) -> str:
    path = unquote(urlparse(url).path).lower()
    if path.endswith(".pdf"):
        return ".pdf"
    if path.endswith(".zip") or "competencia_documento_zip_down.php" in path:
        return ".zip"
    return ".pdf"


def is_candidate_document(url: str, text: str) -> bool:
    haystack = f"{url} {text}".lower()
    path = unquote(urlparse(url).path).lower()
    if any(keyword in haystack for keyword in RESULT_KEYWORDS):
        return path.endswith((".pdf", ".zip")) or "competencia_documento_zip_down.php" in path
    # FECHIDA exposes some competition document bundles without useful anchor text.
    return "registro.fechida.org" in urlparse(url).netloc and "competencia_documento_zip_down.php" in path


def extract_documents(html: str, base_url: str) -> list[Document]:
    parser = AnchorParser()
    parser.feed(html)
    documents: list[Document] = []
    seen: set[str] = set()
    for anchor in parser.anchors:
        absolute_url = urljoin(base_url, anchor["href"])
        if absolute_url in seen or not is_candidate_document(absolute_url, anchor["text"]):
            continue
        seen.add(absolute_url)
        title = anchor["text"] or Path(unquote(urlparse(absolute_url).path)).stem or "documentos-fechida"
        documents.append(Document(absolute_url, title, document_extension(absolute_url)))
    return documents


def infer_year(competition: Competition) -> str:
    for value in (competition.start_date, competition.end_date, competition.title):
        if not value:
            continue
        match = re.search(r"\b(20\d{2})\b", value)
        if match:
            return match.group(1)
    return "unknown_year"


def build_manifest_entries(
    competitions: list[tuple[Competition, list[Document]]],
    pdf_dir: str,
    out_dir_root: str,
    default_source_id: int,
    limit: int,
) -> list[ManifestEntry]:
    entries: list[ManifestEntry] = []
    slug_counts: dict[tuple[str, str, str], int] = {}
    for competition, documents in competitions:
        year = infer_year(competition)
        competition_slug = slugify(competition.title)
        for document in documents:
            if len(entries) >= limit:
                return entries
            title_name = Path(document.title).stem if Path(document.title).suffix else document.title
            title_slug = slugify(title_name)
            if title_slug in {"documentos-fechida", "competencia-documento-zip-down", "documento"}:
                title_slug = f"{competition_slug}-documentos"
            slug_key = (year, competition_slug, title_slug)
            slug_counts[slug_key] = slug_counts.get(slug_key, 0) + 1
            if slug_counts[slug_key] > 1:
                title_slug = f"{title_slug}-{slug_counts[slug_key]}"
            local_name = f"{title_slug}{document.extension}"
            entries.append(
                ManifestEntry(
                    source_url=document.source_url,
                    pdf=str(Path(pdf_dir) / year / competition_slug / local_name),
                    out_dir=str(Path(out_dir_root) / year / competition_slug / title_slug),
                    competition_id=None,
                    default_source_id=default_source_id,
                    fechida_competition_id=competition.competition_id,
                    competition_title=competition.title,
                )
            )
    return entries


def write_jsonl(entries: list[Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(asdict(entry), ensure_ascii=False) for entry in entries]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def discover_from_html(
    list_html: str | None,
    info_html_by_id: dict[int, str],
    id_start: int | None,
    id_end: int | None,
    timeout_seconds: int,
    competitions_url: str,
) -> list[tuple[Competition, list[Document]]]:
    competitions: list[Competition] = []
    if list_html:
        competitions.extend(filter(is_master_competition, parse_competitions_table(list_html, competitions_url)))
    if id_start is not None and id_end is not None:
        for competition_id in range(id_start, id_end + 1):
            url = info_url_for_id(competition_id)
            html = info_html_by_id.get(competition_id)
            if html is None:
                try:
                    html = read_url_text(url, timeout_seconds)
                except Exception:
                    continue
            competition = parse_competition_info(html, competition_id, url)
            if is_master_competition(competition):
                competitions.append(competition)

    discovered: list[tuple[Competition, list[Document]]] = []
    seen_competitions: set[int] = set()
    for competition in competitions:
        if competition.competition_id in seen_competitions:
            continue
        seen_competitions.add(competition.competition_id)
        info_url = competition.info_url or info_url_for_id(competition.competition_id)
        html = info_html_by_id.get(competition.competition_id)
        if html is None:
            html = read_url_text(info_url, timeout_seconds)
        documents = extract_documents(html, info_url)
        if documents:
            discovered.append((competition, documents))
    return discovered


def extract_sheet_gids(html: str) -> list[tuple[str, str]]:
    pattern = re.compile(r'items\.push\(\{name:\s*"([^"]+)",\s*pageUrl:.*?gid:\s*"(\d+)"', re.DOTALL)
    return [(match.group(2), match.group(1)) for match in pattern.finditer(html)]


def published_csv_url(pubhtml_url: str, gid: str | None = None) -> str:
    parsed = urlparse(pubhtml_url)
    path = parsed.path.replace("/pubhtml", "/pub")
    query = {"output": "csv"}
    if gid:
        query["gid"] = gid
    return urlunparse((parsed.scheme, parsed.netloc, path, "", urlencode(query), ""))


MONTHS = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}


def parse_calendar_csv(content: str, source_url: str, gid: str | None = None, sheet_name: str | None = None) -> list[CalendarEvent]:
    rows = list(csv.reader(StringIO(content)))
    year: int | None = None
    month: int | None = None
    active_days: list[int | None] = []
    events: list[CalendarEvent] = []

    for row in rows:
        cells = [normalize_spaces(cell) for cell in row]
        if len(cells) >= 2 and cells[0].isdigit() and cells[1].lower() in MONTHS:
            year = int(cells[0])
            month = MONTHS[cells[1].lower()]
            active_days = []
            continue

        numeric_cells = [int(cell) if cell.isdigit() else None for cell in cells]
        if any(day is not None for day in numeric_cells) and all(cell == "" or cell.isdigit() for cell in cells):
            active_days = numeric_cells
            continue

        if year is None or month is None or not active_days:
            continue
        for index, cell in enumerate(cells):
            day = active_days[index] if index < len(active_days) else None
            if day is None:
                continue
            match = re.search(r"\b(NC)\s*:\s*(.+)", cell, re.IGNORECASE)
            if not match or not MASTER_PATTERN.search(match.group(2)):
                continue
            events.append(
                CalendarEvent(
                    date=f"{year:04d}-{month:02d}-{day:02d}",
                    name=normalize_spaces(match.group(2)),
                    discipline=match.group(1).upper(),
                    source_url=source_url,
                    gid=gid,
                    sheet_name=sheet_name,
                )
            )
    return events


def extract_calendar_iframe_url(html: str, base_url: str = DEFAULT_CALENDAR_URL) -> str | None:
    match = re.search(r'<iframe[^>]+src="([^"]+docs\.google\.com/spreadsheets/[^"]+)"', html, re.IGNORECASE)
    return urljoin(base_url, match.group(1).replace("&amp;", "&")) if match else None


def discover_calendar_events(calendar_html: str, timeout_seconds: int) -> list[CalendarEvent]:
    iframe_url = extract_calendar_iframe_url(calendar_html)
    if not iframe_url:
        return []
    pubhtml = read_url_text(iframe_url, timeout_seconds)
    gids = extract_sheet_gids(pubhtml)
    if not gids:
        csv_url = published_csv_url(iframe_url)
        return parse_calendar_csv(read_url_text(csv_url, timeout_seconds), csv_url)

    events: list[CalendarEvent] = []
    for gid, sheet_name in gids:
        csv_url = published_csv_url(iframe_url, gid)
        events.extend(parse_calendar_csv(read_url_text(csv_url, timeout_seconds), csv_url, gid=gid, sheet_name=sheet_name))
    return events


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Descubre resultados y calendario Master FECHIDA sin descargar PDFs ni cargar a core."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    results = subparsers.add_parser("results", help="Genera manifest JSONL de documentos candidatos FECHIDA Master.")
    source_group = results.add_mutually_exclusive_group()
    source_group.add_argument("--html-file", help="HTML local de campeonatos-natacion.")
    source_group.add_argument("--url", default=DEFAULT_COMPETITIONS_URL, help="URL de campeonatos FECHIDA.")
    results.add_argument("--manifest", required=True, help="Ruta del manifest JSONL a escribir.")
    results.add_argument("--pdf-dir", default=str(BACKEND_DIR / "data" / "raw" / "results_pdf" / "fechida"))
    results.add_argument("--out-dir-root", default=str(BACKEND_DIR / "data" / "raw" / "results_csv" / "fechida"))
    results.add_argument("--probe-id-start", type=int, help="Primer id campeonato-info a sondear.")
    results.add_argument("--probe-id-end", type=int, help="Ultimo id campeonato-info a sondear.")
    results.add_argument("--default-source-id", type=int, default=1)
    results.add_argument("--limit", type=int, default=sys.maxsize)
    results.add_argument("--timeout-seconds", type=int, default=30)
    results.add_argument("--json", action="store_true")

    calendar = subparsers.add_parser("calendar", help="Extrae calendario NC Master desde Google Sheet publicado.")
    calendar.add_argument("--html-file", help="HTML local de calendario-por-mes.")
    calendar.add_argument("--url", default=DEFAULT_CALENDAR_URL, help="URL de calendario por mes FECHIDA.")
    calendar.add_argument("--output-json", required=True, help="Ruta JSON auditable a escribir.")
    calendar.add_argument("--timeout-seconds", type=int, default=30)
    calendar.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "results":
        list_html = Path(args.html_file).read_text(encoding="utf-8") if args.html_file else read_url_text(args.url, args.timeout_seconds)
        discovered = discover_from_html(
            list_html=list_html,
            info_html_by_id={},
            id_start=args.probe_id_start,
            id_end=args.probe_id_end,
            timeout_seconds=args.timeout_seconds,
            competitions_url=args.url if not args.html_file else DEFAULT_COMPETITIONS_URL,
        )
        entries = build_manifest_entries(discovered, args.pdf_dir, args.out_dir_root, args.default_source_id, args.limit)
        write_jsonl(entries, Path(args.manifest))
        payload: dict[str, Any] = {"state": "discovered", "manifest_path": args.manifest, "documents": len(entries)}
    else:
        calendar_html = Path(args.html_file).read_text(encoding="utf-8") if args.html_file else read_url_text(args.url, args.timeout_seconds)
        events = discover_calendar_events(calendar_html, args.timeout_seconds)
        output_path = Path(args.output_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps([asdict(event) for event in events], ensure_ascii=False, indent=2), encoding="utf-8")
        payload = {"state": "discovered", "output_json": args.output_json, "events": len(events)}

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"Estado scraper FECHIDA: {payload['state']}")
        print(f"Registros: {payload.get('documents', payload.get('events', 0))}")


if __name__ == "__main__":
    main()
