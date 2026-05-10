import json
import sys
from argparse import Namespace
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = BACKEND_DIR / "scripts"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import scrape_fchmn as scraper


def test_discover_pdf_urls_resolves_relative_links_skips_duplicates_and_filters_results():
    html = (FIXTURES_DIR / "fchmn_page.html").read_text(encoding="utf-8")

    urls = scraper.discover_pdf_urls(html, "https://fchmn.cl/resultados/", include_keywords=["resultado"])

    assert urls == [
        "https://fchmn.cl/wp-content/uploads/2026/03/resultados-ii-copa-chile-1.pdf",
        "https://fchmn.cl/wp-content/uploads/2026/03/resultados-coppa-italia-master-2026.pdf",
        "https://fchmn.cl/wp-content/uploads/2026/04/resultados-1a-etapa.pdf",
    ]


def test_discover_pdf_urls_can_include_all_pdfs():
    html = (FIXTURES_DIR / "fchmn_page.html").read_text(encoding="utf-8")

    urls = scraper.discover_pdf_urls(html, "https://fchmn.cl/resultados/")

    assert "https://fchmn.cl/wp-content/uploads/2026/04/convocatoria-xiii-copa-penamaster-2026.pdf" in urls


def test_default_discovery_does_not_depend_on_resultado_keyword(monkeypatch):
    html_by_url = {
        "https://fchmn.cl/resultados/": """
        <a href="/wp-content/uploads/2025/09/resutados-vi-copa-araucania-master-2025.pdf">typo oficial</a>
        <a href="/wp-content/uploads/2025/09/convocatoria-vi-copa-araucania-master-2025.pdf">convocatoria</a>
        """,
    }

    monkeypatch.setattr(scraper, "read_url_html", lambda url, timeout_seconds: html_by_url[url])
    manifest_path = BACKEND_DIR / "data" / "staging" / "csv" / "test_scraper_no_keyword_manifest.jsonl"
    manifest_path.unlink(missing_ok=True)
    args = [
        "scrape_fchmn.py",
        "--url",
        "https://fchmn.cl/resultados/",
        "--manifest",
        str(manifest_path),
        "--pdf-dir",
        "backend/data/raw/results_pdf/fchmn",
        "--out-dir-root",
        "backend/data/raw/results_csv/fchmn",
    ]
    monkeypatch.setattr(sys, "argv", args)

    try:
        scraper.main()
        entries = [json.loads(line) for line in manifest_path.read_text(encoding="utf-8").splitlines()]
    finally:
        manifest_path.unlink(missing_ok=True)

    assert [entry["source_url"] for entry in entries] == [
        "https://fchmn.cl/wp-content/uploads/2025/09/resutados-vi-copa-araucania-master-2025.pdf",
        "https://fchmn.cl/wp-content/uploads/2025/09/convocatoria-vi-copa-araucania-master-2025.pdf",
    ]


def test_wordpress_page_url_builds_paginated_urls_from_home():
    assert scraper.wordpress_page_url("https://fchmn.cl/", 1) == "https://fchmn.cl/"
    assert scraper.wordpress_page_url("https://fchmn.cl/", 2) == "https://fchmn.cl/page/2/"


def test_merge_discovered_pdf_urls_deduplicates_across_pages():
    page_one = """
    <a href="/wp-content/uploads/2026/03/resultados-a.pdf">A</a>
    <a href="/wp-content/uploads/2026/03/resultados-b.pdf">B</a>
    """
    page_two = """
    <a href="/wp-content/uploads/2026/03/resultados-b.pdf">B duplicado</a>
    <a href="/wp-content/uploads/2026/03/resultados-c.pdf">C</a>
    """

    urls = scraper.merge_discovered_pdf_urls(
        [(page_one, "https://fchmn.cl/"), (page_two, "https://fchmn.cl/page/2/")],
        include_keywords=["resultado"],
    )

    assert urls == [
        "https://fchmn.cl/wp-content/uploads/2026/03/resultados-a.pdf",
        "https://fchmn.cl/wp-content/uploads/2026/03/resultados-b.pdf",
        "https://fchmn.cl/wp-content/uploads/2026/03/resultados-c.pdf",
    ]


def test_repeated_url_sources_are_merged_without_duplicate_pdfs(monkeypatch):
    html_by_url = {
        "https://fchmn.cl/resultados/": """
        <a href="/wp-content/uploads/2026/03/resultados-a.pdf">A</a>
        <a href="/wp-content/uploads/2026/03/resultados-b.pdf">B</a>
        """,
        "https://fchmn.cl/sudamericanos-master/": """
        <a href="/wp-content/uploads/2026/03/resultados-b.pdf">B</a>
        <a href="/wp-content/uploads/2026/03/resultados-c.pdf">C</a>
        """,
    }

    monkeypatch.setattr(scraper, "read_url_html", lambda url, timeout_seconds: html_by_url[url])
    manifest_path = BACKEND_DIR / "data" / "staging" / "csv" / "test_scraper_multi_url_manifest.jsonl"
    manifest_path.unlink(missing_ok=True)
    args = [
        "scrape_fchmn.py",
        "--url",
        "https://fchmn.cl/resultados/",
        "--url",
        "https://fchmn.cl/sudamericanos-master/",
        "--manifest",
        str(manifest_path),
        "--pdf-dir",
        "backend/data/raw/results_pdf/fchmn",
        "--out-dir-root",
        "backend/data/raw/results_csv/fchmn",
    ]
    monkeypatch.setattr(sys, "argv", args)

    try:
        scraper.main()
        entries = [json.loads(line) for line in manifest_path.read_text(encoding="utf-8").splitlines()]
    finally:
        manifest_path.unlink(missing_ok=True)
    assert [entry["source_url"] for entry in entries] == [
        "https://fchmn.cl/wp-content/uploads/2026/03/resultados-a.pdf",
        "https://fchmn.cl/wp-content/uploads/2026/03/resultados-b.pdf",
        "https://fchmn.cl/wp-content/uploads/2026/03/resultados-c.pdf",
    ]


def test_build_manifest_entries_uses_stable_local_paths():
    args = Namespace(
        pdf_dir="backend/data/raw/results_pdf/fchmn",
        out_dir_root="backend/data/raw/results_csv/fchmn",
        year=None,
        competition_id=42,
        default_source_id=7,
        limit=10,
    )
    urls = [
        "https://fchmn.cl/wp-content/uploads/2026/03/resultados-ii-copa-chile-1.pdf",
        "https://fchmn.cl/wp-content/uploads/2026/03/resultados-coppa-italia-master-2026.pdf",
    ]

    entries = scraper.build_manifest_entries(args, urls)

    assert [entry.source_url for entry in entries] == urls
    assert [entry.pdf for entry in entries] == [
        str(Path("backend/data/raw/results_pdf/fchmn/2026/resultados-ii-copa-chile-1.pdf")),
        str(Path("backend/data/raw/results_pdf/fchmn/2026/resultados-coppa-italia-master-2026.pdf")),
    ]
    assert [entry.out_dir for entry in entries] == [
        str(Path("backend/data/raw/results_csv/fchmn/2026/resultados-ii-copa-chile-1")),
        str(Path("backend/data/raw/results_csv/fchmn/2026/resultados-coppa-italia-master-2026")),
    ]
    assert entries[0].competition_id == 42
    assert entries[0].default_source_id == 7


def test_build_manifest_entries_can_override_year():
    args = Namespace(
        pdf_dir="backend/data/raw/results_pdf/fchmn",
        out_dir_root="backend/data/raw/results_csv/fchmn",
        year=2025,
        competition_id=None,
        default_source_id=1,
        limit=1,
    )

    entries = scraper.build_manifest_entries(
        args,
        ["https://fchmn.cl/wp-content/uploads/2026/03/resultados-ii-copa-chile-1.pdf"],
    )

    assert entries[0].pdf == str(Path("backend/data/raw/results_pdf/fchmn/2025/resultados-ii-copa-chile-1.pdf"))
    assert entries[0].out_dir == str(Path("backend/data/raw/results_csv/fchmn/2025/resultados-ii-copa-chile-1"))


def test_build_manifest_entries_deduplicates_same_slug_only_within_year():
    args = Namespace(
        pdf_dir="backend/data/raw/results_pdf/fchmn",
        out_dir_root="backend/data/raw/results_csv/fchmn",
        year=None,
        competition_id=None,
        default_source_id=1,
        limit=10,
    )
    urls = [
        "https://fchmn.cl/wp-content/uploads/2025/03/resultados-finales.pdf",
        "https://fchmn.cl/wp-content/uploads/2026/03/resultados-finales.pdf",
        "https://fchmn.cl/wp-content/uploads/2026/04/resultados-finales.pdf",
    ]

    entries = scraper.build_manifest_entries(args, urls)

    assert [entry.pdf for entry in entries] == [
        str(Path("backend/data/raw/results_pdf/fchmn/2025/resultados-finales.pdf")),
        str(Path("backend/data/raw/results_pdf/fchmn/2026/resultados-finales.pdf")),
        str(Path("backend/data/raw/results_pdf/fchmn/2026/resultados-finales-2.pdf")),
    ]
    assert [entry.out_dir for entry in entries] == [
        str(Path("backend/data/raw/results_csv/fchmn/2025/resultados-finales")),
        str(Path("backend/data/raw/results_csv/fchmn/2026/resultados-finales")),
        str(Path("backend/data/raw/results_csv/fchmn/2026/resultados-finales-2")),
    ]


def test_write_manifest_emits_jsonl():
    args = Namespace(
        pdf_dir="backend/data/raw/results_pdf/fchmn",
        out_dir_root="backend/data/raw/results_csv/fchmn",
        year=None,
        competition_id=None,
        default_source_id=1,
        limit=1,
    )
    entries = scraper.build_manifest_entries(
        args,
        ["https://fchmn.cl/wp-content/uploads/2026/03/resultados-ii-copa-chile-1.pdf"],
    )
    manifest_path = BACKEND_DIR / "data" / "staging" / "csv" / "test_scraper_manifest.jsonl"
    manifest_path.unlink(missing_ok=True)

    try:
        scraper.write_manifest(entries, manifest_path)
        lines = manifest_path.read_text(encoding="utf-8").splitlines()
    finally:
        manifest_path.unlink(missing_ok=True)
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload == {
        "source_url": "https://fchmn.cl/wp-content/uploads/2026/03/resultados-ii-copa-chile-1.pdf",
        "pdf": str(Path("backend/data/raw/results_pdf/fchmn/2026/resultados-ii-copa-chile-1.pdf")),
        "out_dir": str(Path("backend/data/raw/results_csv/fchmn/2026/resultados-ii-copa-chile-1")),
        "competition_id": None,
        "default_source_id": 1,
    }
