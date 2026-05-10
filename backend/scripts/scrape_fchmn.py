#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import unquote, urljoin, urlparse, urlunparse
from urllib.request import urlopen


BACKEND_DIR = Path(__file__).resolve().parents[1]


@dataclass
class ManifestEntry:
    source_url: str
    pdf: str
    out_dir: str
    competition_id: int | None
    default_source_id: int


class PdfLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        for name, value in attrs:
            if name.lower() == "href" and value:
                self.hrefs.append(value)


def read_url_html(url: str, timeout_seconds: int) -> str:
    with urlopen(url, timeout=timeout_seconds) as response:
        encoding = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(encoding, errors="replace")


def read_html(args: argparse.Namespace) -> tuple[str, str]:
    if args.html_file:
        html_path = Path(args.html_file)
        if not html_path.exists() or not html_path.is_file():
            raise SystemExit(f"[ERROR] No existe el HTML: {html_path}")
        return html_path.read_text(encoding="utf-8"), args.base_url

    source_url = args.url[0]
    return read_url_html(source_url, args.timeout_seconds), source_url


def wordpress_page_url(start_url: str, page_number: int) -> str:
    if page_number <= 1:
        return start_url
    parsed = urlparse(start_url)
    base_path = re.sub(r"/page/\d+/?$", "/", parsed.path or "/")
    if not base_path.endswith("/"):
        base_path = f"{base_path}/"
    page_path = urljoin(base_path, f"page/{page_number}/")
    return urlunparse((parsed.scheme, parsed.netloc, page_path, "", "", ""))


def discover_pdf_urls(html: str, base_url: str, include_keywords: list[str] | None = None) -> list[str]:
    parser = PdfLinkParser()
    parser.feed(html)

    urls: list[str] = []
    seen: set[str] = set()
    normalized_keywords = [keyword.lower() for keyword in include_keywords or []]
    for href in parser.hrefs:
        absolute_url = urljoin(base_url, href)
        path = urlparse(absolute_url).path.lower()
        if not path.endswith(".pdf") or absolute_url in seen:
            continue
        if normalized_keywords and not any(keyword in absolute_url.lower() for keyword in normalized_keywords):
            continue
        seen.add(absolute_url)
        urls.append(absolute_url)
    return urls


def merge_discovered_pdf_urls(pages: list[tuple[str, str]], include_keywords: list[str] | None = None) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for html, base_url in pages:
        for url in discover_pdf_urls(html, base_url, include_keywords=include_keywords):
            if url in seen:
                continue
            seen.add(url)
            urls.append(url)
    return urls


def read_paginated_html(args: argparse.Namespace) -> list[tuple[str, str]]:
    pages: list[tuple[str, str]] = []
    for source_url in args.url:
        for page_number in range(1, args.crawl_pages + 1):
            page_url = wordpress_page_url(source_url, page_number)
            try:
                pages.append((read_url_html(page_url, args.timeout_seconds), page_url))
            except HTTPError as exc:
                if exc.code == 404 and page_number > 1:
                    break
                raise
    return pages


def slugify_pdf_url(url: str) -> str:
    parsed = urlparse(url)
    name = Path(unquote(parsed.path)).stem or "documento"
    normalized = unicodedata.normalize("NFKD", name)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_name).strip("-").lower()
    return slug or "documento"


def infer_year_from_url(url: str) -> str:
    path = unquote(urlparse(url).path)
    match = re.search(r"/(20\d{2})(?:/|$)", path)
    return match.group(1) if match else "unknown_year"


def build_manifest_entries(args: argparse.Namespace, urls: list[str]) -> list[ManifestEntry]:
    entries: list[ManifestEntry] = []
    slug_counts: dict[tuple[str, str], int] = {}
    pdf_dir = Path(args.pdf_dir)
    out_dir_root = Path(args.out_dir_root)

    for url in urls[: args.limit]:
        slug = slugify_pdf_url(url)
        year = str(args.year) if args.year else infer_year_from_url(url)
        slug_key = (year, slug)
        slug_counts[slug_key] = slug_counts.get(slug_key, 0) + 1
        if slug_counts[slug_key] > 1:
            slug = f"{slug}-{slug_counts[slug_key]}"
        entries.append(
            ManifestEntry(
                source_url=url,
                pdf=str(pdf_dir / year / f"{slug}.pdf"),
                out_dir=str(out_dir_root / year / slug),
                competition_id=args.competition_id,
                default_source_id=args.default_source_id,
            )
        )
    return entries


def write_manifest(entries: list[ManifestEntry], manifest_path: Path) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(asdict(entry), ensure_ascii=False) for entry in entries]
    manifest_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Descubre enlaces PDF de FCHMN y emite un manifest JSONL local sin descargar ni cargar a core."
    )
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--html-file", help="HTML local ya descargado para descubrir enlaces PDF.")
    source_group.add_argument("--url", action="append", help="URL de una pagina FCHMN desde donde descubrir enlaces PDF. Puede repetirse.")
    parser.add_argument("--base-url", default="https://fchmn.cl/", help="Base URL para resolver enlaces relativos de --html-file.")
    parser.add_argument("--manifest", required=True, help="Ruta del manifest JSONL a escribir.")
    parser.add_argument("--pdf-dir", default=str(BACKEND_DIR / "data" / "raw" / "results_pdf" / "fchmn"))
    parser.add_argument("--out-dir-root", default=str(BACKEND_DIR / "data" / "raw" / "results_csv" / "fchmn"))
    parser.add_argument("--year", type=int, help="Año de competencia para agrupar PDFs y CSVs; si falta, se infiere de la URL.")
    parser.add_argument("--competition-id", type=int)
    parser.add_argument("--default-source-id", type=int, default=1)
    parser.add_argument("--limit", type=int, default=sys.maxsize, help="Maximo de PDFs a incluir.")
    parser.add_argument("--crawl-pages", type=int, default=1, help="Cantidad maxima de paginas WordPress a recorrer desde --url.")
    parser.add_argument("--all-pdfs", action="store_true", help="Compatibilidad: el discovery ya incluye todos los PDFs por defecto.")
    parser.add_argument(
        "--include-keyword",
        action="append",
        help="Keyword requerida en la URL del PDF. Por defecto no filtra por keyword; usar solo para exploraciones acotadas.",
    )
    parser.add_argument("--timeout-seconds", type=int, default=30, help="Timeout para --url.")
    parser.add_argument("--json", action="store_true", help="Imprime resumen como JSON.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    include_keywords = [] if args.all_pdfs else (args.include_keyword or [])
    if args.html_file and args.crawl_pages != 1:
        raise SystemExit("[ERROR] --crawl-pages solo se puede usar con --url.")
    if args.crawl_pages < 1:
        raise SystemExit("[ERROR] --crawl-pages debe ser mayor o igual a 1.")

    if args.crawl_pages > 1:
        urls = merge_discovered_pdf_urls(read_paginated_html(args), include_keywords=include_keywords)
    elif args.url:
        pages = [(read_url_html(source_url, args.timeout_seconds), source_url) for source_url in args.url]
        urls = merge_discovered_pdf_urls(pages, include_keywords=include_keywords)
    else:
        html, base_url = read_html(args)
        urls = discover_pdf_urls(html, base_url, include_keywords=include_keywords)
    entries = build_manifest_entries(args, urls)
    write_manifest(entries, Path(args.manifest))

    payload: dict[str, Any] = {
        "state": "discovered",
        "manifest_path": args.manifest,
        "documents": len(entries),
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"Estado scraper: {payload['state']}")
        print(f"Manifest: {payload['manifest_path']}")
        print(f"Documentos: {payload['documents']}")


if __name__ == "__main__":
    main()
