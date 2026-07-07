import json
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = BACKEND_DIR / "scripts"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
STAGING_DIR = BACKEND_DIR / "data" / "staging" / "csv"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import download_manifest_pdfs as downloader
import scrape_fechida as scraper


def test_parse_competitions_table_filters_master_competitions():
    html = (FIXTURES_DIR / "fechida_campeonatos.html").read_text(encoding="utf-8")

    competitions = scraper.parse_competitions_table(html)
    master_competitions = [competition for competition in competitions if scraper.is_master_competition(competition)]

    assert [competition.competition_id for competition in master_competitions] == [422]
    assert master_competitions[0].title == "Nacional master y pre-master invierno 26"
    assert master_competitions[0].start_date == "2026-07-23"
    assert master_competitions[0].end_date == "2026-07-26"


def test_extract_documents_keeps_result_pdfs_and_fechida_document_bundle():
    html = (FIXTURES_DIR / "fechida_campeonato_info.html").read_text(encoding="utf-8")

    documents = scraper.extract_documents(html, "https://fechida.cl/campeonato-info/?id=422")

    assert [document.source_url for document in documents] == [
        "https://registro.fechida.org/competencia_documento_zip_down.php?id=497&clave=6a3466dbe5ed0",
        "https://fechida.cl/wp-content/uploads/2026/07/resultados-primera-etapa.pdf",
    ]
    assert [document.extension for document in documents] == [".zip", ".pdf"]


def test_build_manifest_entries_uses_fechida_paths_and_metadata():
    competition = scraper.Competition(
        competition_id=422,
        title="Nacional master y pre-master invierno 26",
        start_date="2026-07-23",
    )
    documents = [
        scraper.Document(
            source_url="https://fechida.cl/wp-content/uploads/2026/07/resultados-primera-etapa.pdf",
            title="resultados primera etapa.pdf",
            extension=".pdf",
        )
    ]

    entries = scraper.build_manifest_entries(
        [(competition, documents)],
        pdf_dir="backend/data/raw/results_pdf/fechida",
        out_dir_root="backend/data/raw/results_csv/fechida",
        default_source_id=3,
        limit=10,
    )

    assert len(entries) == 1
    assert entries[0].source_url == documents[0].source_url
    assert entries[0].pdf == str(
        Path(
            "backend/data/raw/results_pdf/fechida/2026/nacional-master-y-pre-master-invierno-26/resultados-primera-etapa.pdf"
        )
    )
    assert entries[0].out_dir == str(
        Path("backend/data/raw/results_csv/fechida/2026/nacional-master-y-pre-master-invierno-26/resultados-primera-etapa")
    )
    assert entries[0].competition_scope == "fechida_master"
    assert entries[0].source_system == "fechida"
    assert entries[0].fechida_competition_id == 422
    assert entries[0].default_source_id == 3


def test_parse_calendar_csv_extracts_only_nc_master_events():
    csv_content = (FIXTURES_DIR / "fechida_calendar.csv").read_text(encoding="utf-8")

    events = scraper.parse_calendar_csv(
        csv_content,
        "https://docs.google.com/spreadsheets/d/e/demo/pub?output=csv&gid=1072824117",
        gid="1072824117",
        sheet_name="Julio 2026",
    )

    assert events == [
        scraper.CalendarEvent(
            date="2026-07-23",
            name="NACIONAL MASTER DE INVIERNO",
            discipline="NC",
            source_url="https://docs.google.com/spreadsheets/d/e/demo/pub?output=csv&gid=1072824117",
            gid="1072824117",
            sheet_name="Julio 2026",
        )
    ]


def test_discover_results_manifest_is_download_manifest_compatible(monkeypatch):
    list_html = (FIXTURES_DIR / "fechida_campeonatos.html").read_text(encoding="utf-8")
    info_html = (FIXTURES_DIR / "fechida_campeonato_info.html").read_text(encoding="utf-8")
    manifest_path = STAGING_DIR / "test_fechida_manifest.jsonl"
    pdf_path = STAGING_DIR / "downloaded_fechida_result.pdf"
    manifest_path.unlink(missing_ok=True)
    pdf_path.unlink(missing_ok=True)

    def fake_read_url_text(url, timeout_seconds):
        if url.endswith("campeonatos-natacion/"):
            return list_html
        if "campeonato-info" in url:
            return info_html
        raise AssertionError(url)

    monkeypatch.setattr(scraper, "read_url_text", fake_read_url_text)
    discovered = scraper.discover_from_html(
        list_html=list_html,
        info_html_by_id={},
        id_start=None,
        id_end=None,
        timeout_seconds=5,
        competitions_url="https://fechida.cl/campeonatos-natacion/",
    )
    entries = scraper.build_manifest_entries(
        discovered,
        pdf_dir=str(STAGING_DIR),
        out_dir_root=str(STAGING_DIR / "csv"),
        default_source_id=1,
        limit=1,
    )
    entries[0].pdf = str(pdf_path)

    try:
        scraper.write_jsonl(entries, manifest_path)
        manifest_entry = json.loads(manifest_path.read_text(encoding="utf-8").splitlines()[0])
        assert manifest_entry["source_system"] == "fechida"
        assert manifest_entry["competition_scope"] == "fechida_master"

        result = downloader.process_manifest(
            manifest_path,
            timeout_seconds=5,
            fetcher=lambda url, timeout: b"%PDF-1.4\nfechida\n",
        )
    finally:
        manifest_path.unlink(missing_ok=True)

    try:
        assert result.state == "downloaded"
        assert pdf_path.read_bytes() == b"%PDF-1.4\nfechida\n"
    finally:
        pdf_path.unlink(missing_ok=True)
