#!/usr/bin/env python3
from __future__ import annotations

import argparse
from difflib import SequenceMatcher
import hashlib
import json
import re
import sys
from dataclasses import dataclass, asdict
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from natacion_chile.domain.normalization import (
    derive_result_time_ms,
    normalize_athlete_gender,
    normalize_controlled_lower,
    normalize_event_gender,
    normalize_result_status as normalize_domain_result_status,
    normalize_string,
    normalize_stroke as normalize_domain_stroke,
    normalize_swim_time_text,
)

PARSER_VERSION = "0.1.20"

try:
    import pdfplumber
except ImportError as exc:  # pragma: no cover
    raise SystemExit("[ERROR] Falta pdfplumber. Instálalo con: pip install pdfplumber openpyxl") from exc


TIME_OR_STATUS_PATTERN = (
    r"(?:X)?(?:\d{1,2}:\d{2}:\d{2}(?:[\.,]\d+)?|\d{1,3}:\d{2}(?:[\.,]\d+)?[A-Z]?|\d{1,3}'\d{2}'\d{1,2}|\d{1,3}(?:[\.,']\d+)?|NT|NS|DNS|DNF|DQ|DSQ|DFS)"
)
TRAILING_TIME_OR_STATUS_RE = re.compile(
    rf"^(?P<team>.+?)\s+(?P<seed>{TIME_OR_STATUS_PATTERN})$",
    re.IGNORECASE,
)
DATE_DMY_RE = re.compile(r"(?P<day>\d{1,2})[-/](?P<month>\d{1,2})[-/](?P<year>\d{4})")
COMPETITION_HEADER_WITH_DATE_RE = re.compile(
    r"^(?P<name>.+?)\s+-\s+(?P<date>\d{1,2}[-/]\d{1,2}[-/]\d{4})$"
)
COMPETITION_HEADER_WITH_DATE_RANGE_RE = re.compile(
    r"^(?P<name>.+?)\s+-\s+(?P<start_date>\d{1,2}[-/]\d{1,2}[-/]\d{4})\s+(?:a|to)\s+(?P<end_date>\d{1,2}[-/]\d{1,2}[-/]\d{4})$",
    re.IGNORECASE,
)

EVENT_HEADER_RE = re.compile(
    r"^\(?Event\s+(?P<event_number>\d+)\s+(?P<gender>Women|Men|Mixed)\s+(?P<age_group>.+?)\s+(?P<distance_raw>\d+(?:x\d+)?)\s+(?P<course>LC|SC)\s+Meter\s+(?P<stroke>.+?)\)?$",
    re.IGNORECASE,
)

SPANISH_EVENT_HEADER_RE = re.compile(
    r"^\(?Evento\s+(?P<event_number>\d+)\s+(?P<gender>Mujeres|Hombres|Damas|Varones|Mixto)\s+(?P<age_group>.+?)\s+(?P<distance_raw>\d+(?:x\d+)?)\s+(?P<course>CL|CP|CC|LC|SC)\s+Metros?\s+(?P<stroke>.+?)\)?$",
    re.IGNORECASE,
)

SPANISH_RELAY_EVENT_HEADER_RE = re.compile(
    r"^\(?Evento\s+(?P<event_number>\d+)\s+(?P<gender>Mujeres|Hombres|Damas|Varones|Mixto)\s+(?P<age_group>.+?)\s+(?P<distance_raw>\d+x\d+)\s+(?P<course>CL|CP|CC|LC|SC)\s+Metros?\s+Relevo\s+(?P<stroke>.+?)\)?$",
    re.IGNORECASE,
)

SPANISH_RELAY_AGE_SUFFIX_EVENT_HEADER_RE = re.compile(
    r"^\(?Evento\s+(?P<event_number>\d+)\s+(?P<gender>Mujeres|Hombres|Mixto)\s+(?P<distance_raw>\d+)\s+(?P<course>CL|CP|CC)\s+Metro\s+\d+x\d+\s+(?P<stroke>comb|libre)\s+(?P<age_group>\d+\s+a(?:ñ|n)os)\s+Relevo\)?$",
    re.IGNORECASE,
)

HASH_EVENT_HEADER_RE = re.compile(
    r"^\#(?P<event_number>\d+)\s+(?P<gender>Women|Men|Mixed)\s+(?P<age_group>.+?)\s+(?P<distance_raw>\d+(?:x\d+)?)\s+Meter\s+(?P<stroke>.+?)$",
    re.IGNORECASE,
)

COMBINED_EVENT_HEADER_RE = re.compile(
    r"^(?P<gender>Women|Men|Mujeres|Hombres|Damas|Varones)\s+(?P<age_group>.+?)\s+Quadathlon$",
    re.IGNORECASE,
)

COMBINED_TIME_TOKEN_RE = re.compile(
    r"^(?:X)?(?:\d{1,3}[:']\d{2}(?:[\.,']\d{1,2})?|\d{1,3}[\.,']\d{1,2}|NT|NS|DNS|DNF|DQ|DSQ|DFS|-)$",
    re.IGNORECASE,
)

BRAZIL_EVENT_HEADER_RE = re.compile(
    r"^(?P<event_number>\d+)[ªº]\s+PROVA\s+-\s+(?:(?P<relay>REVEZAMENTO)\s+)?(?:(?P<relay_distance>\d+X\d+)\s+)?(?P<distance>\d+)?\s*METROS\s+(?P<stroke>LIVRE|MEDLEY|COSTAS|PEITO|BORBOLETA)\s+(?P<gender>FEMININO|MASCULINO|MISTO)",
    re.IGNORECASE,
)
BRAZIL_AGE_GROUP_RE = re.compile(r"^FAIXA:\s*(?P<age_group>(?:PRÉ\s*)?\d+\s*\+)", re.IGNORECASE)

RESULT_LINE_RE = re.compile(
    rf"^(?P<rank>\*?\d+|---)\s+(?P<name>.+?)\s+(?P<age>\d{{1,3}})\s+(?P<team>.+?)\s+(?P<seed>{TIME_OR_STATUS_PATTERN})\s+(?P<final>{TIME_OR_STATUS_PATTERN})(?:\s+(?P<points>\d+(?:[\.,]\s*\d+)?))?$",
    re.IGNORECASE,
)

RESULT_NO_SEED_LINE_RE = re.compile(
    rf"^(?P<rank>\*?\d+|---)\s+(?P<name>.+?)\s+(?P<age>\d{{1,3}})\s+(?P<team>.+?)\s+(?P<final>{TIME_OR_STATUS_PATTERN})(?:\s+(?P<points>\d+(?:[\.,]\s*\d+)?))?$",
    re.IGNORECASE,
)

FRAGMENTED_TOKEN_RE = re.compile(r"(?<!\S)(?:[A-Za-zÁÉÍÓÚáéíóúÑñÜü]\s+){3,}[A-Za-zÁÉÍÓÚáéíóúÑñÜü](?!\S)")
FRAGMENTED_WORD_WITH_PREFIX_RE = re.compile(r"\b(?P<prefix>[A-Za-zÁÉÍÓÚáéíóúÑñÜü]{2})\s+(?P<tail>(?:[A-Za-zÁÉÍÓÚáéíóúÑñÜü]\s+){2,}[A-Za-zÁÉÍÓÚáéíóúÑñÜü])\b")
FRAGMENTED_TIME_RE = re.compile(r"\b(?P<minute>\d)\s*:\s*(?P<tens>\d)\s+(?P<ones>\d)\s*,\s*(?P<hundred_tens>\d)\s+(?P<hundred_ones>\d)\b")
FRAGMENTED_AGE_TEAM_RE = re.compile(r"\b(?P<age_tens>\d)\s+(?P<age_ones>\d)\s+(?P<team>(?:[A-ZÑ]\s+){2,}[A-ZÑ])\b")

RELAY_TEAM_RE = re.compile(
    rf"^(?P<rank>\*?\d+|---)\s+(?P<team>.+?)\s+(?:(?P<seed>{TIME_OR_STATUS_PATTERN})\s+)?(?P<final>{TIME_OR_STATUS_PATTERN})(?:\s+(?P<points>\d+(?:[\.,]\s*\d+)?))?$",
    re.IGNORECASE,
)

RELAY_SWIMMER_STUCK_LEG_RE = re.compile(
    r"(?P<age_marker>[WM](?:1[8-9]|[2-9]\d|10\d))(?=[1-4]\))",
    re.IGNORECASE,
)

RELAY_SWIMMER_LEG_MARKER_RE = re.compile(
    r"(?<![A-Za-z0-9])(?P<leg>[1-4])(?:[A-Z])?(?:\)\.?\s*|\s+)",
    re.IGNORECASE,
)

RELAY_SWIMMER_SEGMENT_RE = re.compile(
    r"^(?P<name>.+?)(?:\s+(?P<gender>[WM])?(?P<age>\d{1,3})\)?)?$",
    re.IGNORECASE,
)
RELAY_SWIMMER_EMBEDDED_NEXT_RE = re.compile(
    r"^(?P<name>.+?)\s+(?P<gender>[WM])(?P<age>\d{2})(?:\d\)|\)\s*\d)\s*(?P<next_name>.+?)(?:\s+(?P<next_gender>[WM])(?P<next_age>\d{1,3})\)?)?$",
    re.IGNORECASE,
)
RELAY_CONTINUATION_GENDER_AGE_RE = re.compile(r"\s(?P<gender>[WM])(?P<age>\d{1,3})(?=\s|$)", re.IGNORECASE)
LETTER_CHARS = "A-Za-zÁÉÍÓÚÜÑáéíóúüñ"

HEADER_SKIP_PATTERNS = [
    re.compile(r"HY-TEK'?S MEET MANAGER", re.IGNORECASE),
    re.compile(r"^\d+(?:\.\d+)?\s+-\s+\d{1,2}:\d{2}\s+[AP]M\s+\d{2}-\d{2}-\d{4}\s+Page\s+\d+$", re.IGNORECASE),
    re.compile(r"^Results\s*$", re.IGNORECASE),
    re.compile(r"^Results\s*-", re.IGNORECASE),
    re.compile(r"^Resultados\s*$", re.IGNORECASE),
    re.compile(r"^Resultados\s*-", re.IGNORECASE),
    re.compile(r"^(?:Combined Events|Eventos combinados)$", re.IGNORECASE),
    re.compile(r"^Name\s+Age\s+Team\s+Seed\s+Time\s+Finals\s+Time(?:\s+Points)?$", re.IGNORECASE),
    re.compile(r"^Name\s+Age\s+Team\s+Finals\s+Time(?:\s+Points)?$", re.IGNORECASE),
    re.compile(r"^Team\s+Relay\s+Seed\s+Time\s+Finals\s+Time(?:\s+Points)?$", re.IGNORECASE),
    re.compile(r"^Nombre\s+Edad\s+Equipo\s+Tiempo\s+de\s+Finales(?:\s+Puntos)?$", re.IGNORECASE),
    re.compile(r"^Nombre\s+Edad\s+Equipo\s+Seed\s+Time\s+Finals\s+Time(?:\s+Puntos)?$", re.IGNORECASE),
    re.compile(r"^Nombre\s+Edad\s+Equipo\s+Tiempo\s+para\s+Sembrado\s*Tiempo\s+de\s+Finales(?:\s+Puntos)?$", re.IGNORECASE),
    re.compile(r"^Equipo\s+Relevo\s+Tiempo\s+para\s+Sembrado\s*Tiempo\s+de\s+Finales(?:\s+Puntos)?$", re.IGNORECASE),
    re.compile(r"^Place\s+Name\s+Team\s+Total\s+50FLY\s+50BK\s+50BR\s+50FR$", re.IGNORECASE),
    re.compile(r"^Lugar\s+Nombre\s+Equipo\s+Total\s+50FLY\s+50BK\s+50BR\s+50FR$", re.IGNORECASE),
    re.compile(r"^Estadio ", re.IGNORECASE),
    re.compile(r"^Page\s+\d+$", re.IGNORECASE),
    re.compile(r"^P[aá]gina\s+\d+$", re.IGNORECASE),
    re.compile(r"^.+\s+-\s+\d{1,2}[-/]\d{1,2}[-/]\d{4}$", re.IGNORECASE),
    re.compile(r"^.+\s+-\s+\d{1,2}[-/]\d{1,2}[-/]\d{4}\s+(?:a|to)\s+\d{1,2}[-/]\d{1,2}[-/]\d{4}$", re.IGNORECASE),
    re.compile(r"^\(?(?:Combined\s+Team\s+Scores|Scores\s+-|Puntajes\s+-)", re.IGNORECASE),
    re.compile(r"^R\.[MS]\.:", re.IGNORECASE),
    re.compile(r"^(?:\d{1,3}(?::\d{2})?[\.,]\d+\s+)+\d{1,3}(?::\d{2})?[\.,]\d+$", re.IGNORECASE),
    re.compile(r"^(?:Women|Men|Mujeres|Hombres)\s+-\s+.*(?:Team\s+Rankings|Lugar\s+por\s+Equipo)", re.IGNORECASE),
    re.compile(r"^\d+\.\s+.+\s+\d+(?:[\.,]\d+)?(?:\s+\d+\.\s+.+\s+\d+(?:[\.,]\d+)?)?$", re.IGNORECASE),
    # Líneas explicativas HY-TEK para DQ/DNF; el resultado ya queda en la fila del nadador.
    re.compile(r"^(?:DNF|DQ)\s+No\s+", re.IGNORECASE),
    re.compile(r"^SW\d+(?:\.\d+)*\s+", re.IGNORECASE),
]


@dataclass
class EventContext:
    event_number: int
    gender: str
    age_group: str
    distance_label: str
    distance_m: int
    course_code: str
    stroke: str

    @property
    def event_name(self) -> str:
        return f"{self.gender} {self.age_group} {self.distance_label} {self.course_code} Meter {self.stroke}"

    @property
    def is_relay(self) -> bool:
        return "relay" in self.stroke.lower() or "relay" in self.event_name.lower()


@dataclass
class ParsedResultRow:
    page_number: int
    line_number: int
    event_number: int
    event_name: str
    athlete_name: str
    age_at_event: Optional[int]
    birth_year_estimated: Optional[int]
    club_name: str
    rank_position: Optional[str]
    seed_time_text: Optional[str]
    seed_time_ms: Optional[str]
    result_time_text: Optional[str]
    result_time_ms: Optional[str]
    status: Optional[str]
    points: Optional[str]
    raw_line: str


@dataclass
class ParsedRelayTeamRow:
    page_number: int
    line_number: int
    event_number: int
    event_name: str
    relay_team_name: str
    club_name: Optional[str]
    rank_position: Optional[str]
    seed_time_text: Optional[str]
    seed_time_ms: Optional[str]
    result_time_text: Optional[str]
    result_time_ms: Optional[str]
    status: Optional[str]
    points: Optional[str]
    raw_line: str


@dataclass
class ParsedRelaySwimmerRow:
    page_number: int
    line_number: int
    event_number: int
    event_name: str
    relay_team_name: Optional[str]
    leg_order: int
    swimmer_name: str
    gender: Optional[str]
    age_at_event: Optional[int]
    birth_year_estimated: Optional[int]
    raw_line: str


@dataclass
class ParseStats:
    pages_read: int = 0
    event_headers_found: int = 0
    result_rows_found: int = 0
    relay_team_rows_found: int = 0
    relay_swimmer_rows_found: int = 0
    lines_skipped: int = 0
    lines_unparsed: int = 0


ACCENTED = "ÁÉÍÓÚáéíóúÑñÜü"

def clean_extracted_text(value: str | None) -> str | None:
    if value is None:
        return None

    value = unicodedata.normalize("NFC", str(value))

    # arreglos simples ya detectados
    replacements = {
        "NÑ": "Ñ",
        "nñ": "ñ",
        "Penñ": "Peñ",
        "Munñ": "Muñ",
        "Espanñ": "Españ",
        "Canñ": "Cañ",
        "Vinñ": "Viñ",
        "Natacioán": "Natación",
        "Natacioón": "Natación",
        "N(cid:450) i": "Ñi",
        "N(cid:450) u": "Ñu",
        "n(cid:450) i": "ñi",
        "n(cid:450) u": "ñu",
        "Ñ u": "Ñu",
        "ñ u": "ñu",
        "Ñ a": "Ña",
        "ñ a": "ña",
        "Ñ o": "Ño",
        "ñ o": "ño",
        "Ñ e": "Ñe",
        "ñ e": "ñe",
        "Ñ i": "Ñi",
        "ñ i": "ñi",
        "Joseí": "José"
    }
    for bad, good in replacements.items():
        value = value.replace(bad, good)

    # Corrige artefactos frecuentes de tildes mal extraídas en nombres propios
    value = re.sub(r"oí(?=[bcdfghjklmnñpqrstvwxyzBCDFGHJKLMNÑPQRSTVWXYZ])", "ó", value)
    value = re.sub(r"aí(?=[bcdfghjklmnñpqrstvwxyzBCDFGHJKLMNÑPQRSTVWXYZ])", "á", value)
    value = re.sub(r"eí(?=[bcdfghjklmnñpqrstvwxyzBCDFGHJKLMNÑPQRSTVWXYZ])", "é", value)

    # Variante con espacio artificial: "Andre ís" -> "Andrés"
    value = re.sub(r"o\s+í(?=[bcdfghjklmnñpqrstvwxyzBCDFGHJKLMNÑPQRSTVWXYZ])", "ó", value)
    value = re.sub(r"a\s+í(?=[bcdfghjklmnñpqrstvwxyzBCDFGHJKLMNÑPQRSTVWXYZ])", "á", value)
    value = re.sub(r"e\s+í(?=[bcdfghjklmnñpqrstvwxyzBCDFGHJKLMNÑPQRSTVWXYZ])", "é", value)

    # corrige duplicación frecuente tipo "Rocíío" -> "Rocío"
    value = re.sub(r"íi", "í", value)
    value = re.sub(r"íí", "í", value)
    value = re.sub(r"ÍI", "Í", value)
    value = re.sub(r"áa", "á", value)
    value = re.sub(r"ée", "é", value)
    value = re.sub(r"óo", "ó", value)
    value = re.sub(r"úu", "ú", value)
    value = re.sub(r"ÁA", "Á", value)
    value = re.sub(r"ÉE", "É", value)
    value = re.sub(r"ÓO", "Ó", value)
    value = re.sub(r"ÚU", "Ú", value)

    # corrige vocal acentuada suelta al final de palabra anterior:
    # "Alumine í" -> "Aluminé"
    value = re.sub(r"([A-Za-zÑñ])e\s+í\b", r"\1é", value)
    value = re.sub(r"([A-Za-zÑñ])o\s+í\b", r"\1ó", value)

    # espacios múltiples
    value = re.sub(r"\s+", " ", value).strip()

    return value if value else None


CANONICAL_ATHLETE_NAME_TOKENS = {
    "Abraham": "Abraham",
    "Alexandra": "Alexandra",
    "Anais": "Anaís",
    "Andrea": "Andrea",
    "Andres": "Andrés",
    "Angelica": "Angélica",
    "Ariadna": "Ariadna",
    "Bascunan": "Bascuñán",
    "Becerra": "Becerra",
    "Belen": "Belén",
    "Berroeta": "Berroeta",
    "Bocaz": "Bocaz",
    "Briceño": "Briceño",
    "Cabaret": "Cabaret",
    "Caceres": "Cáceres",
    "Cañete": "Cañete",
    "Cañas": "Cañas",
    "Cardenas": "Cárdenas",
    "Carolina": "Carolina",
    "Casassus": "Casassus",
    "Castro": "Castro",
    "Catalina": "Catalina",
    "Cerda": "Cerda",
    "Claudia": "Claudia",
    "Contreras": "Contreras",
    "Cordova": "Córdova",
    "Corvalan": "Corvalán",
    "Cortes": "Cortés",
    "Cristian": "Cristián",
    "Cristobal": "Cristóbal",
    "Daniel": "Daniel",
    "Diaz": "Díaz",
    "Droguett": "Droguett",
    "Echeverria": "Echeverría",
    "Eduardo": "Eduardo",
    "Elizabeth": "Elizabeth",
    "Erika": "Erika",
    "Espinoza": "Espinoza",
    "Fabricio": "Fabricio",
    "Felipe": "Felipe",
    "Fernanda": "Fernanda",
    "Fernandez": "Fernández",
    "Fuenzalida": "Fuenzalida",
    "Gabriela": "Gabriela",
    "Galvez": "Gálvez",
    "Garate": "Gárate",
    "Garcia": "García",
    "Gonzalez": "González",
    "Guzman": "Guzmán",
    "Gutierrez": "Gutiérrez",
    "Hardy": "Hardy",
    "Hector": "Héctor",
    "Henriquez": "Henríquez",
    "Hermosilla": "Hermosilla",
    "Hernan": "Hernán",
    "Jacqueline": "Jacqueline",
    "Jaime": "Jaime",
    "Jeldes": "Jeldes",
    "Jimenez": "Jiménez",
    "Jose": "José",
    "Job": "Job",
    "Karina": "Karina",
    "Labra": "Labra",
    "Lopez": "López",
    "Lourdes": "Lourdes",
    "Lukas": "Lukas",
    "Magaly": "Magaly",
    "Manuel": "Manuel",
    "Marcelo": "Marcelo",
    "Maria": "María",
    "Mario": "Mario",
    "Martin": "Martín",
    "Martinez": "Martínez",
    "Matias": "Matías",
    "Maurice": "Maurice",
    "Mauricio": "Mauricio",
    "Mendez": "Méndez",
    "Menadier": "Menadier",
    "Monica": "Mónica",
    "Montecinos": "Montecinos",
    "Montoya": "Montoya",
    "Mueller": "Müller",
    "Muller": "Müller",
    "Muñoz": "Muñoz",
    "Murua": "Murúa",
    "Navarro": "Navarro",
    "Nicolas": "Nicolás",
    "Nunez": "Núñez",
    "Olivares": "Olivares",
    "Ordenes": "Órdenes",
    "Orieta": "Orieta",
    "Pamela": "Pamela",
    "Panotto": "Panotto",
    "Paola": "Paola",
    "Patricio": "Patricio",
    "Paz": "Paz",
    "Perez": "Pérez",
    "Pia": "Pía",
    "Pilar": "Pilar",
    "Provoste": "Provoste",
    "Quilapan": "Quilapan",
    "Raul": "Raúl",
    "Ramirez": "Ramírez",
    "Rodigo": "Rodrigo",
    "Rodriguez": "Rodríguez",
    "Rondon": "Rondón",
    "Samuel": "Samuel",
    "Salfate": "Salfate",
    "Sanchez": "Sánchez",
    "Sanz": "Sanz",
    "Saez": "Sáez",
    "Schwarzemberg": "Schwarzemberg",
    "Sebastian": "Sebastián",
    "Sepulveda": "Sepúlveda",
    "Silvia": "Silvia",
    "Sofia": "Sofía",
    "Sonia": "Sonia",
    "Tania": "Tania",
    "Teran": "Terán",
    "Tomas": "Tomás",
    "Torrealba": "Torrealba",
    "Valdes": "Valdés",
    "Valentina": "Valentina",
    "Vasquez": "Vásquez",
    "Velasquez": "Velásquez",
    "Veronica": "Verónica",
    "Victor": "Víctor",
    "Vicente": "Vicente",
    "Vigouroux": "Vigouroux",
    "Villegas": "Villegas",
    "Yanez": "Yáñez",
}
CANONICAL_ATHLETE_NAME_TOKEN_KEYS = {
    re.sub(r"[^a-z]", "", unicodedata.normalize("NFD", key).encode("ascii", "ignore").decode("ascii").lower()): value
    for key, value in CANONICAL_ATHLETE_NAME_TOKENS.items()
}
NAME_CONNECTOR_TOKENS = {"da", "de", "del", "di", "do", "dos", "la", "las", "lo", "los", "van", "von", "y"}


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text)
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn")


def _name_token_key(text: str) -> str:
    return re.sub(r"[^a-z]", "", _strip_accents(text).lower())


def _name_token_consonant_skeleton(text: str) -> str:
    return re.sub(r"[aeiou]", "", _name_token_key(text))


def _generate_athlete_token_variants(token: str) -> list[str]:
    variants = {token}
    compact = token.replace(" ", "")
    variants.add(compact)

    vowel_chars = "AEIOUÁÉÍÓÚaeiouáéíóú"
    for current in list(variants):
        for idx in range(len(current) - 1):
            left = current[idx]
            right = current[idx + 1]
            if left in vowel_chars and right in vowel_chars and (_strip_accents(left).lower() != _strip_accents(right).lower() or left != right):
                variants.add(current[:idx] + current[idx + 1 :])
                variants.add(current[: idx + 1] + current[idx + 2 :])

    return [variant for variant in variants if variant]


def _collapse_fragmented_name_side(side: str) -> str:
    tokens = side.split()
    if len(tokens) <= 1:
        return side

    merged: list[str] = []
    idx = 0
    while idx < len(tokens):
        current = tokens[idx]
        while idx + 1 < len(tokens):
            nxt = tokens[idx + 1]
            nxt_key = _name_token_key(nxt)
            current_key = _name_token_key(current)
            if not nxt_key:
                break
            if nxt[:1].islower():
                current += nxt
                idx += 1
                continue
            if len(current_key) == 1:
                current += nxt
                idx += 1
                continue
            if (
                len(nxt_key) <= 2
                and nxt_key not in NAME_CONNECTOR_TOKENS
                and len(current_key) >= 4
                and nxt[:1].islower()
            ):
                current += nxt
                idx += 1
                continue
            break
        merged.append(current)
        idx += 1
    return " ".join(merged)


def _looks_suspicious_athlete_token(token: str) -> bool:
    return (
        bool(re.search(r"[ÁÉÍÓÚáéíóú].*[ÁÉÍÓÚáéíóú]", token))
        or bool(re.search(r"[aeiouáéíóú][ÁÉÍÓÚáéíóú]|[ÁÉÍÓÚáéíóú][aeiouáéíóú]", token))
        or "ñ" in token.lower()
        or "ññ" in token.lower()
        or "eñ" in token.lower()
        or len(token) != len(_strip_accents(token))
    )


def _preserve_token_case(original: str, canonical: str) -> str:
    if original.isupper():
        return canonical.upper()
    if original.islower():
        return canonical.lower()
    return canonical


def _repair_athlete_name_token(match: re.Match[str]) -> str:
    token = match.group(0)
    key = _name_token_key(token)
    if len(key) <= 2:
        return token

    suspicious = _looks_suspicious_athlete_token(token)
    canonical = CANONICAL_ATHLETE_NAME_TOKEN_KEYS.get(key)
    if canonical and suspicious:
        return _preserve_token_case(token, canonical)

    if not suspicious:
        return token

    best_ratio = 0.0
    best_canonical = None
    for variant in _generate_athlete_token_variants(token):
        variant_key = _name_token_key(variant)
        skeleton = _name_token_consonant_skeleton(variant)
        if not variant_key or not skeleton:
            continue
        exact = CANONICAL_ATHLETE_NAME_TOKEN_KEYS.get(variant_key)
        if exact:
            return _preserve_token_case(token, exact)

        for candidate_key, candidate in CANONICAL_ATHLETE_NAME_TOKEN_KEYS.items():
            if not candidate_key or candidate_key[:1] != variant_key[:1]:
                continue
            if _name_token_consonant_skeleton(candidate) != skeleton:
                continue
            if abs(len(candidate_key) - len(variant_key)) > 2:
                continue
            ratio = SequenceMatcher(None, variant_key, candidate_key).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_canonical = candidate

    if best_canonical and best_ratio >= 0.72:
        return _preserve_token_case(token, best_canonical)
    return token


def clean_athlete_name(value: str | None) -> str | None:
    value = clean_extracted_text(value)
    if value is None:
        return None
    value = value.replace("Mª", "Maria")
    value = value.replace("M?", "Maria")
    value = value.replace("(cid:976)", "f")
    # OCR/layout artifacts observed inside names, not source-authored suffixes
    # like "Rojas, 2".
    value = re.sub(r"\s*\|\s*(?=,)", "", value)
    value = re.sub(r"(?<=[A-Za-zÁÉÍÓÚáéíóúÑñ])\d+(?=,\s*[A-Za-zÁÉÍÓÚáéíóúÑñ])", "", value)

    def collapse_prefixed_vowel_artifact(match: re.Match[str]) -> str:
        first = match.group(1)
        second = match.group(2)
        if _strip_accents(first).lower() == _strip_accents(second).lower():
            return second
        return match.group(0)

    # OCR can duplicate the opening vowel of a word, for example
    # "AÁlvarez". Keep the accented leading vowel.
    value = re.sub(
        r"\b([AEIOUaeiou])([ÁÉÍÓÚáéíóú])(?=[A-Za-zÁÉÍÓÚáéíóúÑñ])",
        collapse_prefixed_vowel_artifact,
        value,
    )

    token_fixes = [
        (r"\bJose(?:[áóú])?\b", "José"),
        (r"\bMaríóa\b", "María"),
        (r"\bGarcíóa\b", "García"),
        (r"\bMari(?:óa|ía)\b", "María"),
        (r"\bMaríáa\b", "Maríá"),
        (r"\bAndre(?:ás|és|ós)\b", "Andrés"),
        (r"\bCristia(?:án|én)\b", "Cristián"),
        (r"\bBele(?:án|én|ún)\b", "Belén"),
        (r"\bHe(?:á|ó)ctor\b", "Héctor"),
        (r"\bCristo(?:é|ó)bal\b", "Cristóbal"),
        (r"\bIvaén\b", "Iván"),
        (r"\bSa(?:á|í|ó)ez\b", "Sáez"),
        (r"\bAlarco(?:án|én)\b", "Alarcón"),
        (r"\bRamí(?:á|ó)rez\b", "Ramírez"),
        (r"\bVictor\b", "Víctor"),
        (r"\bTiller(?:ia|ía|íéa)\b", "Tillería"),
        (r"\bCanto(?:á|é|í|ó)\b", "Canto"),
        (r"\bAÁlvarez\b", "Álvarez"),
        (r"\bA[ÁÓ]vila\b", "Ávila"),
    ]
    for pattern_text, replacement in token_fixes:
        value = re.sub(pattern_text, replacement, value, flags=re.IGNORECASE)

    value = re.sub(r"\s*ñ\s+ñ\s*", "ñ", value, flags=re.IGNORECASE)
    value = ", ".join(_collapse_fragmented_name_side(side.strip()) for side in value.split(","))
    value = re.sub(
        r"\b([AEIOUaeiou])([ÁÉÍÓÚáéíóú])(?=[A-Za-zÁÉÍÓÚáéíóúÑñ])",
        collapse_prefixed_vowel_artifact,
        value,
    )
    value = re.sub(r"[A-Za-zÁÉÍÓÚáéíóúÑñ]+", _repair_athlete_name_token, value)
    value = re.sub(r"\s+", " ", value).strip()
    return value if value else None


def normalize_course_code(value: Optional[str]) -> Optional[str]:
    value = normalize_string(value)
    if value is None:
        return None
    key = value.upper()
    mapping = {
        "LC": "LC",
        "SC": "SC",
        "CL": "LC",
        "CP": "SC",
        "CC": "SC",
    }
    return mapping.get(key, key)


def normalize_stroke(value: Optional[str]) -> Optional[str]:
    value = normalize_string(value)
    if value is None:
        return None
    # Limpieza propia del layout PDF: algunos encabezados pegan categorias de edad al estilo.
    value = re.sub(
        r"\s+(?:(?:\d+\s+a\s+\d+|\d+\s+y\s+(?:m[aá]s|\d+)|\d+)\s+a(?:ñ|n)os|\d+\s+a(?:ñ|n)os\s+y\s+m[aá]s)(?=\s+relay$|$)",
        "",
        value,
        flags=re.IGNORECASE,
    )
    return normalize_domain_stroke(value)


def parse_dmy_date(value: Optional[str]) -> Optional[str]:
    value = normalize_string(value)
    if value is None:
        return None
    m = DATE_DMY_RE.search(value)
    if not m:
        return None
    return f"{int(m.group('year')):04d}-{int(m.group('month')):02d}-{int(m.group('day')):02d}"


def parse_competition_header(line: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    candidate = normalize_string(line)
    if candidate is None:
        return None, None, None
    if re.search(r"HY-TEK|MEET MANAGER|\bPage\s+\d+\b|\bP[aá]gina\s+\d+\b|^Results\b|^Resultados\b|^Event\s+\d+\b|^Evento\s+\d+\b", candidate, re.IGNORECASE):
        return None, None, None

    m = COMPETITION_HEADER_WITH_DATE_RANGE_RE.match(candidate)
    if m:
        name = clean_extracted_text(m.group("name"))
        return name, parse_dmy_date(m.group("start_date")), parse_dmy_date(m.group("end_date"))

    # Encabezado FCHMN/HY-TEK usual: "VI Torneo Smart Swim Team - 24-05-2025".
    m = COMPETITION_HEADER_WITH_DATE_RE.match(candidate)
    if m:
        name = clean_extracted_text(m.group("name"))
        date_iso = parse_dmy_date(m.group("date"))
        return name, date_iso, date_iso

    if (candidate.startswith("II Copa") or candidate.startswith("I Copa")) or "Copa" in candidate:
        return clean_extracted_text(candidate), None, None
    return None, None, None


def derive_competition_year(metadata: Dict[str, Optional[str]], pdf_path: Optional[Path] = None) -> Optional[int]:
    candidates = [
        metadata.get("competition_start_date"),
        metadata.get("competition_end_date"),
        metadata.get("competition_name"),
        metadata.get("results_label"),
    ]
    if pdf_path is not None:
        candidates.append(pdf_path.name)
    for candidate in candidates:
        if not candidate:
            continue
        years = re.findall(r"(19\d{2}|20\d{2}|21\d{2})", str(candidate))
        if years:
            return int(years[-1])
    return None


def parse_distance_to_meters(distance_raw: Optional[str]) -> Optional[int]:
    distance_raw = normalize_string(distance_raw)
    if distance_raw is None:
        return None
    m = re.fullmatch(r"(\d+)x(\d+)", distance_raw.lower())
    if m:
        return int(m.group(1)) * int(m.group(2))
    if distance_raw.isdigit():
        return int(distance_raw)
    return None


def parse_brazil_event_header(line: str) -> Optional[EventContext]:
    candidate = normalize_string(line)
    if candidate is None:
        return None
    m = BRAZIL_EVENT_HEADER_RE.match(candidate)
    if not m:
        return None

    is_relay = bool(m.group("relay"))
    distance_label = (m.group("relay_distance") or m.group("distance") or "").lower()
    stroke_raw = m.group("stroke").lower()
    stroke_map = {
        "livre": "freestyle_relay" if is_relay else "freestyle",
        "medley": "medley_relay" if is_relay else "individual_medley",
        "costas": "backstroke",
        "peito": "breaststroke",
        "borboleta": "butterfly",
    }
    gender_map = {"feminino": "women", "masculino": "men", "misto": "mixed"}
    return EventContext(
        event_number=int(m.group("event_number")),
        gender=gender_map[m.group("gender").lower()],
        age_group="open",
        distance_label=distance_label,
        distance_m=parse_distance_to_meters(distance_label) or 0,
        course_code="SC",
        stroke=stroke_map[stroke_raw],
    )


def parse_brazil_age_group(line: str) -> Optional[str]:
    candidate = normalize_string(line)
    if candidate is None:
        return None
    m = BRAZIL_AGE_GROUP_RE.match(candidate)
    if not m:
        return None
    return re.sub(r"\s+", "", m.group("age_group").replace("PRÉ", "pre"))


def with_event_age_group(ctx: EventContext, age_group: str) -> EventContext:
    return EventContext(
        event_number=ctx.event_number,
        gender=ctx.gender,
        age_group=age_group,
        distance_label=ctx.distance_label,
        distance_m=ctx.distance_m,
        course_code=ctx.course_code,
        stroke=ctx.stroke,
    )


def info(msg: str) -> None:
    print(f"[INFO] {msg}")


def warn(msg: str) -> None:
    print(f"[WARN] {msg}")


def fail(msg: str) -> None:
    print(f"[ERROR] {msg}", file=sys.stderr)
    raise SystemExit(1)


def normalize_result_status(status, result_time_text):
    normalized = normalize_domain_result_status(status, result_time_text)
    if normalized != "unknown":
        return normalized
    rtt = normalize_string(result_time_text)
    if rtt:
        upper = rtt.upper()
        if upper in {"NT", "NS", "UNKNOWN"}:
            return "unknown"
        if upper.startswith("X"):
            return "unknown"
        if derive_result_time_ms(rtt) is not None:
            return "valid"
        return "valid"

    return "unknown"


def looks_like_hytek_points_as_final(seed_raw: Optional[str], final_raw: Optional[str], max_points: int = 9) -> bool:
    seed_time_ms = derive_result_time_ms(seed_raw)
    final_time_ms = derive_result_time_ms(final_raw)
    if seed_time_ms is None or final_time_ms is None:
        return False
    # In HY-TEK rows with no seed, the generic two-time regex can read
    # "real final time + points" as "seed + final".
    return seed_time_ms > 9000 and final_time_ms <= max_points * 1000


def looks_like_hytek_spurious_seed_before_two_times(
    seed_raw: Optional[str], final_raw: Optional[str], points_raw: Optional[str]
) -> bool:
    seed_time_ms = derive_result_time_ms(seed_raw)
    final_time_ms = derive_result_time_ms(final_raw)
    points_time_ms = derive_result_time_ms(points_raw)
    if seed_time_ms is None or final_time_ms is None or points_time_ms is None:
        return False
    return seed_time_ms < 25000 and final_time_ms >= 25000 and points_time_ms >= 25000


def looks_like_hytek_spurious_seed_before_status_and_final(
    seed_raw: Optional[str], final_raw: Optional[str], points_raw: Optional[str]
) -> bool:
    seed_time_ms = derive_result_time_ms(seed_raw)
    points_time_ms = derive_result_time_ms(points_raw)
    final_key = normalize_match_text(final_raw)
    return (
        seed_time_ms is not None
        and seed_time_ms < 25000
        and final_key in {"nt", "dns", "dnf", "dq", "dsq"}
        and points_time_ms is not None
        and points_time_ms >= 25000
    )


def should_keep_status_seed_attached_to_team(seed_raw: Optional[str], final_raw: Optional[str]) -> bool:
    seed_key = normalize_match_text(seed_raw)
    final_key = normalize_match_text(final_raw)
    if not seed_key or not final_key:
        return False
    return seed_key == final_key


def should_drop_status_trailing_time_as_points(final_raw: Optional[str], points_raw: Optional[str]) -> bool:
    final_key = normalize_match_text(final_raw)
    points_time_ms = derive_result_time_ms(points_raw)
    return final_key in {"dns", "dnf", "dq", "dsq"} and points_time_ms is not None and points_time_ms >= 10000


def should_drop_unranked_status_points(rank_raw: str, final_raw: Optional[str]) -> bool:
    final_key = normalize_match_text(final_raw)
    final_text = normalize_string(final_raw)
    return rank_raw.strip() == "---" and (
        final_key in {"dns", "dnf", "dq", "dsq"} or (isinstance(final_text, str) and final_text.upper().startswith("X"))
    )


def is_implausible_seed_for_distance(seed_time_text: Optional[str], distance_m: int) -> bool:
    seed_time_ms = derive_result_time_ms(seed_time_text)
    return distance_m >= 100 and seed_time_ms is not None and seed_time_ms < 25000


def format_result_time_ms(result_time_ms: int) -> str:
    centiseconds = result_time_ms // 10
    minutes, centiseconds = divmod(centiseconds, 6000)
    seconds, centis = divmod(centiseconds, 100)
    if minutes:
        return f"{minutes}:{seconds:02d},{centis:02d}"
    return f"{seconds},{centis:02d}"


def repair_combined_split_times(total_token: Optional[str], split_times: List[str]) -> List[str]:
    normalized_splits = [normalize_swim_time_text(raw_time) for raw_time in split_times]
    total_time_ms = derive_result_time_ms(total_token)
    split_time_ms = [derive_result_time_ms(raw_time) for raw_time in normalized_splits]
    short_indexes = [index for index, value in enumerate(split_time_ms) if value is not None and value < 10000]
    if total_time_ms is None or len(short_indexes) != 1:
        return [value or raw for value, raw in zip(normalized_splits, split_times)]
    if any(value is None for index, value in enumerate(split_time_ms) if index not in short_indexes):
        return [value or raw for value, raw in zip(normalized_splits, split_times)]

    short_index = short_indexes[0]
    inferred_time_ms = total_time_ms - sum(value or 0 for index, value in enumerate(split_time_ms) if index != short_index)
    if inferred_time_ms <= 9000:
        return [value or raw for value, raw in zip(normalized_splits, split_times)]
    normalized_splits[short_index] = format_result_time_ms(inferred_time_ms)
    return [value or raw for value, raw in zip(normalized_splits, split_times)]



def should_skip_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    return any(p.search(stripped) for p in HEADER_SKIP_PATTERNS)



def parse_event_header(line: str) -> Optional[EventContext]:
    candidate = clean_extracted_text(line.strip()) or line.strip()
    candidate = re.sub(r"^E\s+vento\b", "Evento", candidate, flags=re.IGNORECASE)
    m = EVENT_HEADER_RE.match(candidate)
    if not m:
        m = SPANISH_EVENT_HEADER_RE.match(candidate)
    if not m:
        m = SPANISH_RELAY_EVENT_HEADER_RE.match(candidate)
    if not m:
        m = SPANISH_RELAY_AGE_SUFFIX_EVENT_HEADER_RE.match(candidate)
    if not m:
        m = HASH_EVENT_HEADER_RE.match(candidate)
    if not m:
        return None
    course_raw = m.groupdict().get("course") or "SC"
    course_code = normalize_course_code(course_raw) or course_raw.upper()
    stroke_raw = m.group("stroke")
    if m.re is SPANISH_RELAY_EVENT_HEADER_RE:
        stroke_raw = f"relevo {stroke_raw}"
    if m.re is SPANISH_RELAY_AGE_SUFFIX_EVENT_HEADER_RE:
        stroke_raw = f"{stroke_raw} relevo"
    return EventContext(
        event_number=int(m.group("event_number")),
        gender=normalize_event_gender(m.group("gender")),
        age_group=m.group("age_group").strip(),
        distance_label=m.group("distance_raw"),
        distance_m=parse_distance_to_meters(m.group("distance_raw")) or 0,
        course_code=course_code,
        stroke=normalize_stroke(stroke_raw),
    )


def parse_combined_event_header(line: str, event_number: int) -> Optional[EventContext]:
    candidate = normalize_string(line)
    if candidate is None:
        return None
    m = COMBINED_EVENT_HEADER_RE.match(candidate)
    if not m:
        return None
    return EventContext(
        event_number=event_number,
        gender=normalize_event_gender(m.group("gender")),
        age_group=m.group("age_group").strip(),
        distance_label="50",
        distance_m=50,
        course_code="LC",
        stroke="quadathlon",
    )


def is_combined_time_token(value: str) -> bool:
    return bool(COMBINED_TIME_TOKEN_RE.match(value.strip()))


def parse_combined_result_line(line: str, ctx: EventContext, page_number: int, line_number: int, competition_year: Optional[int]) -> List[ParsedResultRow]:
    tokens = line.strip().split()
    if len(tokens) < 6:
        return []

    time_tokens: List[str] = []
    while tokens and is_combined_time_token(tokens[-1]):
        time_tokens.insert(0, tokens.pop())
    if len(time_tokens) < 4:
        return []

    split_times = time_tokens[-4:]
    total_token = None
    if len(time_tokens) > 4:
        total_token = time_tokens[-5]
        if total_token == "-":
            total_token = None
    split_times = repair_combined_split_times(total_token, split_times)

    rank_position: Optional[str] = None
    if tokens and re.fullmatch(r"\d+", tokens[0]):
        rank_position = tokens.pop(0)

    age_at_event: Optional[int] = None
    if len(tokens) >= 3 and re.fullmatch(r"\d{1,3}", tokens[-2]):
        age_at_event = int(tokens[-2])
        club_name = tokens[-1]
        name_tokens = tokens[:-2]
    elif len(tokens) >= 2:
        club_name = tokens[-1]
        name_tokens = tokens[:-1]
    else:
        return []

    athlete_name = clean_athlete_name(" ".join(name_tokens))
    club_name = clean_extracted_text(club_name)
    if not athlete_name or not club_name:
        return []

    birth_year_estimated = (competition_year - age_at_event) if (competition_year is not None and age_at_event is not None) else None
    strokes = ["butterfly", "backstroke", "breaststroke", "freestyle"]
    rows: List[ParsedResultRow] = []
    for offset, (stroke, raw_time) in enumerate(zip(strokes, split_times), start=1):
        if raw_time == "-":
            continue
        result_time_text = normalize_swim_time_text(raw_time)
        result_time_ms = derive_result_time_ms(result_time_text)
        status = "valid" if result_time_ms is not None else normalize_result_status(None, result_time_text)
        event_ctx = EventContext(
            event_number=ctx.event_number * 10 + offset,
            gender=ctx.gender,
            age_group=ctx.age_group,
            distance_label="50",
            distance_m=50,
            course_code=ctx.course_code,
            stroke=stroke,
        )
        rows.append(
            ParsedResultRow(
                page_number=page_number,
                line_number=line_number,
                event_number=event_ctx.event_number,
                event_name=clean_extracted_text(event_ctx.event_name),
                athlete_name=athlete_name,
                age_at_event=age_at_event,
                birth_year_estimated=birth_year_estimated,
                club_name=club_name,
                rank_position=rank_position,
                seed_time_text=None,
                seed_time_ms=None,
                result_time_text=result_time_text,
                result_time_ms=str(result_time_ms) if result_time_ms is not None else None,
                status=status,
                points=None,
                raw_line=line.strip(),
            )
        )
    return rows



def repair_fragmented_result_line(line: str) -> str:
    if not (FRAGMENTED_TOKEN_RE.search(line) or FRAGMENTED_TIME_RE.search(line)):
        return line

    repaired = FRAGMENTED_TIME_RE.sub(
        lambda m: f"{m.group('minute')}:{m.group('tens')}{m.group('ones')},{m.group('hundred_tens')}{m.group('hundred_ones')}",
        line,
    )

    def collapse_age_team(match: re.Match) -> str:
        team = match.group("team").replace(" ", "")
        return f"{match.group('age_tens')}{match.group('age_ones')} {team}"

    repaired = FRAGMENTED_AGE_TEAM_RE.sub(collapse_age_team, repaired)

    def collapse_word(match: re.Match) -> str:
        return match.group(0).replace(" ", "")

    repaired = FRAGMENTED_TOKEN_RE.sub(collapse_word, repaired)
    repaired = FRAGMENTED_WORD_WITH_PREFIX_RE.sub(lambda m: m.group("prefix") + m.group("tail").replace(" ", ""), repaired)
    repaired = re.sub(r"(?<=,\s)([A-Za-zÁÉÍÓÚáéíóúÑñÜü]{2})\s+([a-záéíóúñü]{3,})\b", r"\1\2", repaired)
    repaired = re.sub(r"(?<=\w)\s+,", ",", repaired)
    repaired = re.sub(r"\s+", " ", repaired).strip()
    return repaired


def event_age_group_starts_at_adult_age(age_group: Optional[str]) -> bool:
    age_group = normalize_string(age_group)
    if age_group is None:
        return False
    match = re.search(r"\d+", age_group)
    if not match:
        return False
    return int(match.group(0)) >= 18


def parse_result_line(line: str, ctx: EventContext, page_number: int, line_number: int, competition_year: Optional[int]) -> Optional[ParsedResultRow]:
    line = repair_fragmented_result_line(line.strip())
    m = RESULT_LINE_RE.match(line)
    has_seed = True
    if not m:
        m = RESULT_NO_SEED_LINE_RE.match(line)
        has_seed = False
    if not m:
        return None

    rank_raw = m.group("rank").strip()
    final_raw = normalize_string(m.group("final"))
    seed_raw = normalize_string(m.group("seed")) if has_seed else None
    team_raw = normalize_string(m.group("team"))
    points_raw = normalize_string(m.groupdict().get("points"))
    if has_seed and points_raw is None and looks_like_hytek_points_as_final(seed_raw, final_raw):
        points_raw = final_raw
        final_raw = seed_raw
        seed_raw = None
        has_seed = False
    elif has_seed and looks_like_hytek_spurious_seed_before_two_times(seed_raw, final_raw, points_raw):
        seed_raw = final_raw
        final_raw = points_raw
        points_raw = None
    elif has_seed and looks_like_hytek_spurious_seed_before_status_and_final(seed_raw, final_raw, points_raw):
        seed_raw = final_raw
        final_raw = points_raw
        points_raw = None
    elif should_drop_status_trailing_time_as_points(final_raw, points_raw):
        points_raw = None
    if points_raw is not None and should_drop_unranked_status_points(rank_raw, final_raw):
        points_raw = None
    if has_seed and seed_raw and derive_result_time_ms(seed_raw) is None and team_raw:
        # Algunos DQ/DNF dejan el seed pegado al club: "Club A 49.33 DQ DQ".
        team_seed_match = TRAILING_TIME_OR_STATUS_RE.match(team_raw)
        if team_seed_match:
            team_raw = team_seed_match.group("team")
            if should_keep_status_seed_attached_to_team(seed_raw, final_raw):
                seed_raw = team_seed_match.group("seed")
    status = normalize_result_status(None, final_raw)
    normalized_final = normalize_swim_time_text(final_raw)
    rank_position: Optional[str] = None if rank_raw == "---" else rank_raw.lstrip("*").lstrip("*")

    if isinstance(normalized_final, str) and normalized_final.upper().startswith("X"):
        rank_position = None

    seed_time_text = normalize_swim_time_text(seed_raw) if has_seed else None
    if is_implausible_seed_for_distance(seed_time_text, ctx.distance_m):
        seed_time_text = None
    seed_time_ms = derive_result_time_ms(seed_time_text)
    result_time_ms = derive_result_time_ms(normalized_final)
    age_at_event = int(m.group("age"))
    if age_at_event < 10 and team_raw and event_age_group_starts_at_adult_age(ctx.age_group):
        # OCR/pdfplumber can duplicate the first digit of an adult age before the club.
        age_team_match = re.match(r"^(?P<age>[1-9]\d)\s+(?P<team>.+)$", team_raw)
        if age_team_match:
            age_at_event = int(age_team_match.group("age"))
            team_raw = age_team_match.group("team")
    birth_year_estimated = (competition_year - age_at_event) if competition_year is not None else None

    return ParsedResultRow(
        page_number=page_number,
        line_number=line_number,
        event_number=ctx.event_number,
        event_name=clean_extracted_text(ctx.event_name),
        athlete_name=clean_athlete_name(m.group("name")),
        age_at_event=age_at_event,
        birth_year_estimated=birth_year_estimated,
        club_name=clean_extracted_text(team_raw),
        rank_position=rank_position,
        seed_time_text=seed_time_text,
        seed_time_ms=str(seed_time_ms) if seed_time_ms is not None else None,
        result_time_text=normalized_final,
        result_time_ms=str(result_time_ms) if result_time_ms is not None else None,
        status=status,
        points=points_raw.replace(" ", "") if isinstance(points_raw, str) else points_raw,
        raw_line=line,
    )



def parse_relay_team_line(line: str, ctx: EventContext, page_number: int, line_number: int) -> Optional[ParsedRelayTeamRow]:
    m = RELAY_TEAM_RE.match(line.strip())
    if not m:
        return None

    rank_raw = m.group("rank").strip()
    seed_raw = normalize_string(m.group("seed"))
    final_raw = normalize_string(m.group("final"))
    points_raw = normalize_string(m.groupdict().get("points"))
    if points_raw is None and looks_like_hytek_points_as_final(seed_raw, final_raw, max_points=18):
        points_raw = final_raw
        final_raw = seed_raw
        seed_raw = None
    elif should_drop_status_trailing_time_as_points(final_raw, points_raw):
        points_raw = None
    if points_raw is not None and should_drop_unranked_status_points(rank_raw, final_raw):
        points_raw = None
    status = normalize_result_status(None, final_raw)
    normalized_final = normalize_swim_time_text(final_raw)
    rank_position: Optional[str] = None if rank_raw == "---" else rank_raw.lstrip("*").lstrip("*")

    if isinstance(normalized_final, str) and normalized_final.upper().startswith("X"):
        rank_position = None

    seed_time_text = normalize_swim_time_text(seed_raw)
    if is_implausible_seed_for_distance(seed_time_text, ctx.distance_m):
        seed_time_text = None
    seed_time_ms = derive_result_time_ms(seed_time_text)
    result_time_ms = derive_result_time_ms(normalized_final)

    return ParsedRelayTeamRow(
        page_number=page_number,
        line_number=line_number,
        event_number=ctx.event_number,
        event_name=clean_extracted_text(ctx.event_name),
        relay_team_name=clean_extracted_text(m.group("team")),
        club_name=None,
        rank_position=rank_position,
        seed_time_text=seed_time_text,
        seed_time_ms=str(seed_time_ms) if seed_time_ms is not None else None,
        result_time_text=normalized_final,
        result_time_ms=str(result_time_ms) if result_time_ms is not None else None,
        status=status,
        points=points_raw.replace(" ", "") if isinstance(points_raw, str) else points_raw,
        raw_line=line.strip(),
    )



def build_relay_swimmer_row(
    ctx: EventContext,
    page_number: int,
    line_number: int,
    relay_team_name: Optional[str],
    competition_year: Optional[int],
    leg_order: int,
    swimmer_name: str,
    gender_raw: str,
    age_at_event: Optional[int],
    raw_line: str,
) -> ParsedRelaySwimmerRow:
    birth_year_estimated = (competition_year - age_at_event) if (competition_year is not None and age_at_event is not None) else None
    return ParsedRelaySwimmerRow(
        page_number=page_number,
        line_number=line_number,
        event_number=ctx.event_number,
        event_name=ctx.event_name,
        relay_team_name=relay_team_name,
        leg_order=leg_order,
        swimmer_name=swimmer_name.strip(),
        gender=normalize_athlete_gender(gender_raw),
        age_at_event=age_at_event,
        birth_year_estimated=birth_year_estimated,
        raw_line=raw_line,
    )


def split_embedded_relay_swimmer(segment: str, expected_next_leg: int) -> Optional[Tuple[str, str, Optional[int], str, str, Optional[int]]]:
    if expected_next_leg > 4:
        return None
    m = RELAY_SWIMMER_EMBEDDED_NEXT_RE.match(segment)
    if not m:
        return None
    first_name = clean_athlete_name(m.group("name"))
    next_name = clean_athlete_name(m.group("next_name"))
    if not first_name or not next_name:
        return None
    if "," not in next_name and len(next_name.split()) < 2:
        return None
    first_gender = (m.group("gender") or "").upper()
    next_gender = (m.group("next_gender") or "").upper()
    first_age = int(m.group("age")) if m.group("age") else None
    next_age = int(m.group("next_age")) if m.group("next_age") else None
    return first_name, first_gender, first_age, next_name, next_gender, next_age


def normalize_embedded_relay_markers(line: str) -> str:
    # OCR can inject the next leg marker inside the previous swimmer age/name:
    # "Angeálica3 W) P6a8saríán" means "... W68 3) Pasaríán".
    line = re.sub(
        rf"(?<=[{LETTER_CHARS}])(?P<leg>[1-4])\s*\)\s*(?P<gender>[WM])\s+",
        r" \g<leg>) ",
        line,
        flags=re.IGNORECASE,
    )
    line = re.sub(
        rf"(?<=[{LETTER_CHARS}])(?P<leg>[1-4])\s+(?P<gender>[WM])\)\s+",
        r" \g<leg>) ",
        line,
        flags=re.IGNORECASE,
    )
    line = re.sub(
        rf"(?P<gender>[WM])(?P<age_tens>\d)(?P<leg>[1-4])\)(?P<age_ones>\d)\s+(?P<next_initial>[WM])\d?\s*(?=[{LETTER_CHARS}])",
        r"\g<gender>\g<age_tens>\g<age_ones> \g<leg>) \g<next_initial>",
        line,
        flags=re.IGNORECASE,
    )
    line = re.sub(
        rf"(?P<gender>[WM])(?P<age_tens>\d)\)(?P<age_ones>\d)\s+(?P<next_initial>[WM])(?P<leg>[1-4])\s+(?=[{LETTER_CHARS}])",
        r"\g<gender>\g<age_tens>\g<age_ones> \g<leg>) \g<next_initial>",
        line,
        flags=re.IGNORECASE,
    )
    return line


def parse_relay_swimmer_line(line: str, ctx: EventContext, page_number: int, line_number: int, relay_team_name: Optional[str], competition_year: Optional[int]) -> List[ParsedRelaySwimmerRow]:
    stripped = line.strip()
    stripped = normalize_embedded_relay_markers(stripped)
    # pdfplumber a veces pega la edad del nadador anterior con el siguiente tramo: "W394)" -> "W39 4)".
    stripped = RELAY_SWIMMER_STUCK_LEG_RE.sub(r"\g<age_marker> ", stripped)
    # En líneas largas también puede deformar el marcador, por ejemplo "4F)."; segmentar evita fusionar nadadores.
    markers = list(RELAY_SWIMMER_LEG_MARKER_RE.finditer(stripped))
    if not markers:
        return []

    swimmers: List[ParsedRelaySwimmerRow] = []
    for index, marker in enumerate(markers):
        next_start = markers[index + 1].start() if index + 1 < len(markers) else len(stripped)
        segment = stripped[marker.end():next_start].strip()
        leg_order = int(marker.group("leg"))
        embedded = split_embedded_relay_swimmer(segment, leg_order + 1)
        if embedded:
            first_name, first_gender, first_age, next_name, next_gender, next_age = embedded
            swimmers.append(
                build_relay_swimmer_row(
                    ctx,
                    page_number,
                    line_number,
                    relay_team_name,
                    competition_year,
                    leg_order,
                    first_name,
                    first_gender or ctx.gender or "",
                    first_age,
                    stripped,
                )
            )
            swimmers.append(
                build_relay_swimmer_row(
                    ctx,
                    page_number,
                    line_number,
                    relay_team_name,
                    competition_year,
                    leg_order + 1,
                    next_name,
                    next_gender or ctx.gender or "",
                    next_age,
                    stripped,
                )
            )
            continue
        m = RELAY_SWIMMER_SEGMENT_RE.match(segment)
        if not m:
            continue
        swimmer_name = clean_athlete_name(m.group("name"))
        if not swimmer_name:
            continue
        gender_raw = (m.group("gender") or ctx.gender or "").upper()
        age_at_event = int(m.group("age")) if m.group("age") else None
        swimmers.append(
            build_relay_swimmer_row(
                ctx,
                page_number,
                line_number,
                relay_team_name,
                competition_year,
                leg_order,
                swimmer_name,
                gender_raw,
                age_at_event,
                stripped,
            )
        )
    return swimmers


def parse_relay_swimmer_continuation_line(
    line: str,
    ctx: EventContext,
    page_number: int,
    line_number: int,
    relay_team_name: Optional[str],
    competition_year: Optional[int],
    starting_leg_order: int,
) -> List[ParsedRelaySwimmerRow]:
    if not relay_team_name or starting_leg_order > 4:
        return []
    stripped = line.strip()
    markers = list(RELAY_CONTINUATION_GENDER_AGE_RE.finditer(stripped))
    if not markers:
        return []

    swimmers: List[ParsedRelaySwimmerRow] = []
    segment_start = 0
    leg_order = starting_leg_order
    for marker in markers:
        if leg_order > 4:
            break
        swimmer_name = clean_athlete_name(stripped[segment_start:marker.start()])
        segment_start = marker.end()
        if not swimmer_name or "," not in swimmer_name:
            return []
        swimmers.append(
            build_relay_swimmer_row(
                ctx,
                page_number,
                line_number,
                relay_team_name,
                competition_year,
                leg_order,
                swimmer_name,
                marker.group("gender").upper(),
                int(marker.group("age")),
                stripped,
            )
        )
        leg_order += 1
    return swimmers


def words_to_text(words: List[dict]) -> str:
    return clean_extracted_text(" ".join(str(word.get("text", "")) for word in words)) or ""


def group_words_by_row(words: List[dict]) -> List[List[dict]]:
    rows: List[List[dict]] = []
    for word in sorted(words, key=lambda item: (float(item["top"]), float(item["x0"]))):
        if not rows or abs(float(rows[-1][0]["top"]) - float(word["top"])) > 2.0:
            rows.append([word])
        else:
            rows[-1].append(word)
    return rows


def row_words_between(words: List[dict], left: float, right: float) -> List[dict]:
    return [word for word in words if left <= float(word["x0"]) < right]


def parse_brazil_result_row(words: List[dict], ctx: EventContext, page_number: int, line_number: int) -> Optional[ParsedResultRow]:
    if not words or ctx.is_relay:
        return None
    rank_raw = str(words[0].get("text", ""))
    if not re.fullmatch(r"\d+º|---|N/C", rank_raw, re.IGNORECASE):
        return None
    if len(words) < 3 or not re.fullmatch(r"\d+", str(words[1].get("text", ""))):
        return None

    athlete_name = clean_athlete_name(words_to_text(row_words_between(words, 120, 316)))
    club_name = words_to_text(row_words_between(words, 316, 412))
    result_raw = words_to_text(row_words_between(words, 412, 450)) or None
    points_raw = words_to_text(row_words_between(words, 450, 472)) or None
    if not athlete_name or not club_name:
        return None

    normalized_result = normalize_swim_time_text(result_raw)
    result_time_ms = derive_result_time_ms(normalized_result)
    status = "valid" if result_time_ms is not None else normalize_result_status(None, normalized_result)
    rank_position = None if rank_raw in {"---", "N/C"} else rank_raw.rstrip("º")
    return ParsedResultRow(
        page_number=page_number,
        line_number=line_number,
        event_number=ctx.event_number,
        event_name=clean_extracted_text(ctx.event_name),
        athlete_name=athlete_name,
        age_at_event=None,
        birth_year_estimated=None,
        club_name=club_name,
        rank_position=rank_position,
        seed_time_text=None,
        seed_time_ms=None,
        result_time_text=normalized_result,
        result_time_ms=str(result_time_ms) if result_time_ms is not None else None,
        status=status,
        points=points_raw.replace(" ", "") if isinstance(points_raw, str) else points_raw,
        raw_line=words_to_text(words),
    )


def parse_brazil_relay_team_row(words: List[dict], ctx: EventContext, page_number: int, line_number: int) -> Optional[ParsedRelayTeamRow]:
    if not words or not ctx.is_relay:
        return None
    rank_raw = str(words[0].get("text", ""))
    if not re.fullmatch(r"\d+º|---|N/C", rank_raw, re.IGNORECASE):
        return None

    team_words = row_words_between(words, 120, 316)
    club_name = words_to_text(row_words_between(words, 316, 412))
    if not club_name and team_words and float(team_words[-1]["x1"]) > 316:
        club_name = clean_extracted_text(str(team_words[-1].get("text", ""))) or ""
        team_words = team_words[:-1]
    relay_team_name = words_to_text(team_words)
    result_raw = words_to_text(row_words_between(words, 412, 450)) or None
    points_raw = words_to_text(row_words_between(words, 450, 472)) or None
    if not relay_team_name or not club_name:
        return None

    normalized_result = normalize_swim_time_text(result_raw)
    result_time_ms = derive_result_time_ms(normalized_result)
    status = "valid" if result_time_ms is not None else normalize_result_status(None, normalized_result)
    rank_position = None if rank_raw in {"---", "N/C"} else rank_raw.rstrip("º")
    return ParsedRelayTeamRow(
        page_number=page_number,
        line_number=line_number,
        event_number=ctx.event_number,
        event_name=clean_extracted_text(ctx.event_name),
        relay_team_name=relay_team_name,
        club_name=club_name,
        rank_position=rank_position,
        seed_time_text=None,
        seed_time_ms=None,
        result_time_text=normalized_result,
        result_time_ms=str(result_time_ms) if result_time_ms is not None else None,
        status=status,
        points=points_raw.replace(" ", "") if isinstance(points_raw, str) else points_raw,
        raw_line=words_to_text(words),
    )


def parse_brazil_relay_swimmer_row(words: List[dict], ctx: EventContext, page_number: int, line_number: int, relay_team_name: Optional[str], leg_order: int) -> Optional[ParsedRelaySwimmerRow]:
    if not words or not ctx.is_relay or relay_team_name is None:
        return None
    if len(words) < 2 or not re.fullmatch(r"\d+", str(words[0].get("text", ""))):
        return None
    swimmer_name = words_to_text(row_words_between(words, 120, 316))
    if not swimmer_name:
        return None
    return ParsedRelaySwimmerRow(
        page_number=page_number,
        line_number=line_number,
        event_number=ctx.event_number,
        event_name=clean_extracted_text(ctx.event_name),
        relay_team_name=relay_team_name,
        leg_order=leg_order,
        swimmer_name=swimmer_name,
        gender=None,
        age_at_event=None,
        birth_year_estimated=None,
        raw_line=words_to_text(words),
    )



def normalize_match_text(value: Optional[str]) -> str:
    value = clean_extracted_text(value)
    if value is None:
        return ""
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def normalize_match_text_without_digits(value: Optional[str]) -> str:
    normalized = normalize_match_text(value)
    normalized = re.sub(r"\d+", "", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def score_from_normalized_names(left_norm: str, right_norm: str) -> float:
    if not left_norm or not right_norm:
        return 0.0
    ratio = SequenceMatcher(None, left_norm, right_norm).ratio()
    left_tokens = {tok for tok in left_norm.split() if len(tok) > 1 and not any(ch.isdigit() for ch in tok)}
    right_tokens = {tok for tok in right_norm.split() if len(tok) > 1 and not any(ch.isdigit() for ch in tok)}
    token_score = 0.0
    if left_tokens and right_tokens:
        token_score = len(left_tokens & right_tokens) / max(len(left_tokens), len(right_tokens))
    return (ratio * 0.65) + (token_score * 0.35)



def name_match_score(left: Optional[str], right: Optional[str]) -> float:
    left_norm = normalize_match_text(left)
    right_norm = normalize_match_text(right)
    if not left_norm or not right_norm:
        return 0.0

    score = score_from_normalized_names(left_norm, right_norm)
    if re.search(r"\d", left_norm + right_norm):
        digitless_score = score_from_normalized_names(
            normalize_match_text_without_digits(left),
            normalize_match_text_without_digits(right),
        )
        score = max(score, digitless_score - 0.03)
    return score



def infer_relay_club_name_for_parser(relay_team_name: Optional[str], club_names: List[str]) -> Optional[str]:
    relay_team_name = clean_extracted_text(relay_team_name)
    if relay_team_name is None:
        return None

    relay_norm = normalize_match_text(relay_team_name)
    direct = {normalize_match_text(name): name for name in club_names if clean_extracted_text(name)}
    if relay_norm in direct:
        return direct[relay_norm]

    suffix_match = re.match(r"^(.*?)(?:\s+[A-Z])$", relay_team_name.strip())
    if suffix_match:
        candidate = normalize_match_text(suffix_match.group(1))
        if candidate in direct:
            return direct[candidate]

    candidates = []
    for original in club_names:
        norm = normalize_match_text(original)
        if norm and (relay_norm == norm or relay_norm.startswith(norm + " ")):
            candidates.append((len(norm), original))
    if candidates:
        candidates.sort(reverse=True)
        return candidates[0][1]
    return None



def reconcile_relay_swimmers_with_individuals(parsed_rows: List[ParsedResultRow], relay_team_rows: List[ParsedRelayTeamRow], relay_swimmer_rows: List[ParsedRelaySwimmerRow]) -> None:
    individual_by_club_gender: Dict[Tuple[str, str], List[ParsedResultRow]] = {}
    club_names: List[str] = []
    seen_club_names = set()
    seen_individual_keys = set()

    for row in parsed_rows:
        club_name = clean_extracted_text(row.club_name)
        athlete_gender = None
        event_match = EVENT_HEADER_RE.match(f"Event {row.event_number} {row.event_name}")
        if event_match:
            athlete_gender = normalize_athlete_gender(event_match.group("gender"))
        club_key = normalize_match_text(club_name)
        gender_key = normalize_athlete_gender(athlete_gender)
        if club_name and club_key not in seen_club_names:
            seen_club_names.add(club_key)
            club_names.append(club_name)
        if club_key and gender_key:
            individual_key = (club_key, gender_key, normalize_match_text(row.athlete_name), row.age_at_event)
            if individual_key in seen_individual_keys:
                continue
            seen_individual_keys.add(individual_key)
            individual_by_club_gender.setdefault((club_key, gender_key), []).append(row)

    relay_club_by_team: Dict[str, Optional[str]] = {}
    for row in relay_team_rows:
        relay_club_by_team[normalize_match_text(row.relay_team_name)] = infer_relay_club_name_for_parser(row.relay_team_name, club_names)

    for row in relay_swimmer_rows:
        relay_club = relay_club_by_team.get(normalize_match_text(row.relay_team_name))
        club_key = normalize_match_text(relay_club)
        gender_key = normalize_athlete_gender(row.gender)
        candidate_entries: List[Tuple[str, ParsedResultRow]] = []
        if gender_key in {"female", "male"}:
            candidate_entries.extend(
                (gender_key, candidate)
                for candidate in individual_by_club_gender.get((club_key, gender_key), [])
            )
        else:
            # Mixed relay events may omit the swimmer gender marker on a segment.
            # In that case, try both person-level genders and let the individual
            # results of the same club disambiguate the swimmer.
            for fallback_gender in ("female", "male"):
                candidate_entries.extend(
                    (fallback_gender, candidate)
                    for candidate in individual_by_club_gender.get((club_key, fallback_gender), [])
                )
        scored_candidates: List[Tuple[float, str, ParsedResultRow]] = []

        for candidate_gender, candidate in candidate_entries:
            score = name_match_score(row.swimmer_name, candidate.athlete_name)
            if row.age_at_event is not None and candidate.age_at_event == row.age_at_event:
                score += 0.10
            elif row.age_at_event is not None and score < 0.82:
                score -= 0.10
            scored_candidates.append((score, candidate_gender, candidate))

        if not scored_candidates:
            continue

        scored_candidates.sort(key=lambda item: item[0], reverse=True)
        best_score, best_gender, best = scored_candidates[0]
        second_score = scored_candidates[1][0] if len(scored_candidates) > 1 else 0.0

        if best_score >= 0.82 and (best_score - second_score) >= 0.12:
            row.swimmer_name = best.athlete_name
            row.gender = best_gender
            row.age_at_event = best.age_at_event
            row.birth_year_estimated = best.birth_year_estimated



def extract_text_lines(pdf_path: Path) -> List[Tuple[int, List[str]]]:
    pages: List[Tuple[int, List[str]]] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_index, page in enumerate(pdf.pages):
            text = page.extract_text(x_tolerance=1.5, y_tolerance=3) or ""
            lines = [ln.rstrip() for ln in text.splitlines()]
            pages.append((page_index + 1, lines))
    return pages


def looks_like_hytek_multicolumn(pages: List[Tuple[int, List[str]]]) -> bool:
    probe_lines = [line for _, lines in pages[:2] for line in lines]
    has_hash_events = any(re.search(r"#\d+\s+(?:Women|Men|Mixed)\s+\d", line) for line in probe_lines)
    has_mixed_columns = any(len(re.findall(r"#\d+\s+(?:Women|Men|Mixed)", line)) > 1 for line in probe_lines)
    return has_hash_events and has_mixed_columns


def looks_like_hytek_two_column(pages: List[Tuple[int, List[str]]]) -> bool:
    probe_lines = [line for _, lines in pages[:2] for line in lines]
    return any(len(re.findall(r"\bEvent\s+\d+\s+(?:Women|Men|Mixed)", line)) > 1 for line in probe_lines)


def parse_hytek_multicolumn_pdf(pdf_path: Path, column_ranges: Optional[List[Tuple[int, int]]] = None):
    text_pages = extract_text_lines(pdf_path)
    stats = ParseStats(pages_read=len(text_pages))
    rows: List[ParsedResultRow] = []
    relay_team_rows: List[ParsedRelayTeamRow] = []
    relay_swimmer_rows: List[ParsedRelaySwimmerRow] = []
    debug_rows: List[Dict[str, Optional[str]]] = []

    competition_name: Optional[str] = None
    results_label: Optional[str] = None
    competition_start_date: Optional[str] = None
    competition_end_date: Optional[str] = None
    for _, lines in text_pages[:2]:
        for line in lines:
            if competition_name is None:
                competition_name, competition_start_date, competition_end_date = parse_competition_header(line)
            if results_label is None and line.lower().startswith("results"):
                results_label = line

    competition_year = derive_competition_year(
        {
            "competition_start_date": competition_start_date,
            "competition_end_date": competition_end_date,
            "competition_name": competition_name,
            "results_label": results_label,
        },
        pdf_path,
    )
    if column_ranges is None:
        column_ranges = [(0, 205), (205, 405), (405, 620)]
    current_event: Optional[EventContext] = None
    last_relay_team_name: Optional[str] = None
    relay_leg_order = 1

    with pdfplumber.open(pdf_path) as pdf:
        for page_index, page in enumerate(pdf.pages, start=1):
            words = page.extract_words(x_tolerance=1.5, y_tolerance=3, keep_blank_chars=False)
            word_rows = list(group_words_by_row(words))
            # HY-TEK multicolumna fluye por columna logica, no por filas fisicas.
            # Si leemos fila->columna, una continuacion de la columna derecha puede
            # quedar asignada al evento viejo antes de ver el encabezado real ubicado
            # mas abajo en la columna anterior (caso LQBLO 2023).
            for _column_index, (left, right) in enumerate(column_ranges):
                for line_number, word_row in enumerate(word_rows, start=1):
                    segment = words_to_text([word for word in word_row if left <= float(word["x0"]) < right])
                    if not segment:
                        continue
                    line = segment.strip()
                    if should_skip_line(line):
                        stats.lines_skipped += 1
                        continue

                    if line.startswith("(") and line.endswith(")"):
                        line = line[1:-1].strip()

                    event = parse_event_header(line)
                    if event is not None:
                        current_event = event
                        last_relay_team_name = None
                        relay_leg_order = 1
                        stats.event_headers_found += 1
                        continue

                    if current_event is None:
                        stats.lines_skipped += 1
                        continue

                    if current_event.is_relay:
                        relay_team = parse_relay_team_line(line, current_event, page_index, line_number)
                        if relay_team is not None:
                            relay_team_rows.append(relay_team)
                            last_relay_team_name = relay_team.relay_team_name
                            relay_leg_order = 1
                            stats.relay_team_rows_found += 1
                            continue

                        relay_swimmers = parse_relay_swimmer_line(
                            line,
                            current_event,
                            page_index,
                            line_number,
                            last_relay_team_name,
                            competition_year,
                        )
                        if relay_swimmers:
                            relay_swimmer_rows.extend(relay_swimmers)
                            relay_leg_order = max(row.leg_order for row in relay_swimmers) + 1
                            stats.relay_swimmer_rows_found += len(relay_swimmers)
                            continue
                        relay_swimmers = parse_relay_swimmer_continuation_line(
                            line,
                            current_event,
                            page_index,
                            line_number,
                            last_relay_team_name,
                            competition_year,
                            relay_leg_order,
                        )
                        if relay_swimmers:
                            relay_swimmer_rows.extend(relay_swimmers)
                            relay_leg_order += len(relay_swimmers)
                            stats.relay_swimmer_rows_found += len(relay_swimmers)
                            continue
                    else:
                        parsed = parse_result_line(line, current_event, page_index, line_number, competition_year)
                        if parsed is not None:
                            rows.append(parsed)
                            stats.result_rows_found += 1
                            continue

                    if re.match(r"^(?:\*?\d+|---)\b", line):
                        stats.lines_unparsed += 1
                        debug_rows.append(
                            {
                                "page_number": page_index,
                                "line_number": line_number,
                                "event_name_context": current_event.event_name,
                                "raw_line": line,
                                "reason": "unparsed_multicolumn_line",
                            }
                        )
                    else:
                        stats.lines_skipped += 1

    reconcile_relay_swimmers_with_individuals(rows, relay_team_rows, relay_swimmer_rows)
    relay_team_rows, relay_swimmer_rows = deduplicate_relay_rows(relay_team_rows, relay_swimmer_rows)
    debug_df = pd.DataFrame(debug_rows, columns=["page_number", "line_number", "event_name_context", "raw_line", "reason"])
    metadata = {
        "pdf_name": pdf_path.name,
        "pdf_sha256": compute_file_sha256(pdf_path),
        "parser_version": PARSER_VERSION,
        "competition_name": competition_name,
        "competition_start_date": competition_start_date,
        "competition_end_date": competition_end_date,
        "results_label": results_label,
        "competition_year": competition_year,
    }
    return rows, relay_team_rows, relay_swimmer_rows, debug_df, stats, metadata


def compute_file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def deduplicate_relay_rows(
    relay_team_rows: List[ParsedRelayTeamRow],
    relay_swimmer_rows: List[ParsedRelaySwimmerRow],
) -> Tuple[List[ParsedRelayTeamRow], List[ParsedRelaySwimmerRow]]:
    seen_teams = set()
    unique_teams: List[ParsedRelayTeamRow] = []
    for row in relay_team_rows:
        key = (
            row.event_name,
            row.club_name,
            row.relay_team_name,
            row.rank_position,
            row.seed_time_text,
            row.seed_time_ms,
            row.result_time_text,
            row.result_time_ms,
            row.points,
            row.status,
        )
        if key in seen_teams:
            continue
        seen_teams.add(key)
        unique_teams.append(row)

    seen_swimmers = set()
    unique_swimmers: List[ParsedRelaySwimmerRow] = []
    for row in relay_swimmer_rows:
        key = (
            row.event_name,
            row.relay_team_name,
            row.leg_order,
            row.swimmer_name,
            row.gender,
            row.age_at_event,
            row.birth_year_estimated,
        )
        if key in seen_swimmers:
            continue
        seen_swimmers.add(key)
        unique_swimmers.append(row)

    return unique_teams, unique_swimmers


def parse_brazil_competition_dates(line: str) -> Tuple[Optional[str], Optional[str]]:
    m = re.search(r"(?P<start_day>\d{1,2})\s+a\s+(?P<end_day>\d{1,2})/(?P<month>\d{1,2})/(?P<year>\d{4})", line)
    if not m:
        return None, None
    year = int(m.group("year"))
    month = int(m.group("month"))
    start_day = int(m.group("start_day"))
    end_day = int(m.group("end_day"))
    return f"{year:04d}-{month:02d}-{start_day:02d}", f"{year:04d}-{month:02d}-{end_day:02d}"


def parse_brazil_pdf(pdf_path: Path):
    stats = ParseStats()
    rows: List[ParsedResultRow] = []
    relay_team_rows: List[ParsedRelayTeamRow] = []
    relay_swimmer_rows: List[ParsedRelaySwimmerRow] = []
    debug_rows: List[Dict[str, Optional[str]]] = []

    competition_name: Optional[str] = None
    competition_start_date: Optional[str] = None
    competition_end_date: Optional[str] = None
    results_label: Optional[str] = None
    current_event_base: Optional[EventContext] = None
    current_event: Optional[EventContext] = None
    last_relay_team_name: Optional[str] = None
    relay_leg_order = 0

    with pdfplumber.open(pdf_path) as pdf:
        stats.pages_read = len(pdf.pages)
        for page_index, page in enumerate(pdf.pages, start=1):
            text = page.extract_text(x_tolerance=1, y_tolerance=3) or ""
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            if results_label is None and lines:
                results_label = lines[0]
            if competition_name is None:
                for line in lines:
                    if "CAMPEONATO SUDAMERICANO" in line:
                        competition_name = clean_extracted_text(line)
                        break
            if competition_start_date is None:
                for line in lines:
                    start_date, end_date = parse_brazil_competition_dates(line)
                    if start_date:
                        competition_start_date = start_date
                        competition_end_date = end_date
                        break

            words = page.extract_words(x_tolerance=1, y_tolerance=3, keep_blank_chars=False)
            for line_number, word_row in enumerate(group_words_by_row(words), start=1):
                row_text = words_to_text(word_row)
                if not row_text:
                    stats.lines_skipped += 1
                    continue

                event = parse_brazil_event_header(row_text)
                if event is not None:
                    current_event_base = event
                    current_event = None
                    last_relay_team_name = None
                    relay_leg_order = 0
                    stats.event_headers_found += 1
                    continue

                age_group = parse_brazil_age_group(row_text)
                if age_group is not None and current_event_base is not None:
                    current_event = with_event_age_group(current_event_base, age_group)
                    last_relay_team_name = None
                    relay_leg_order = 0
                    continue

                if current_event is None:
                    stats.lines_skipped += 1
                    continue

                if re.match(r"^\d+m:", row_text) or row_text.startswith(("RECORDE ", "COL. ", "Associação ")) or "CAMPEONATO SUDAMERICANO" in row_text:
                    stats.lines_skipped += 1
                    continue

                if current_event.is_relay:
                    relay_team = parse_brazil_relay_team_row(word_row, current_event, page_index, line_number)
                    if relay_team is not None:
                        relay_team_rows.append(relay_team)
                        last_relay_team_name = relay_team.relay_team_name
                        relay_leg_order = 0
                        stats.relay_team_rows_found += 1
                        continue

                    relay_leg_order += 1
                    relay_swimmer = parse_brazil_relay_swimmer_row(word_row, current_event, page_index, line_number, last_relay_team_name, relay_leg_order)
                    if relay_swimmer is not None:
                        relay_swimmer_rows.append(relay_swimmer)
                        stats.relay_swimmer_rows_found += 1
                        continue
                    relay_leg_order = max(relay_leg_order - 1, 0)
                else:
                    result = parse_brazil_result_row(word_row, current_event, page_index, line_number)
                    if result is not None:
                        rows.append(result)
                        stats.result_rows_found += 1
                        continue

                if re.match(r"^(?:\d+º|---|N/C)\b", row_text, re.IGNORECASE):
                    stats.lines_unparsed += 1
                    debug_rows.append(
                        {
                            "page_number": page_index,
                            "line_number": line_number,
                            "event_name_context": current_event.event_name,
                            "raw_line": row_text,
                            "reason": "unparsed_brazil_result_line",
                        }
                    )
                else:
                    stats.lines_skipped += 1

    competition_year = derive_competition_year(
        {
            "competition_start_date": competition_start_date,
            "competition_end_date": competition_end_date,
            "competition_name": competition_name,
            "results_label": results_label,
        },
        pdf_path,
    )
    debug_df = pd.DataFrame(debug_rows, columns=["page_number", "line_number", "event_name_context", "raw_line", "reason"])
    metadata = {
        "pdf_name": pdf_path.name,
        "pdf_sha256": compute_file_sha256(pdf_path),
        "parser_version": PARSER_VERSION,
        "competition_name": competition_name,
        "competition_start_date": competition_start_date,
        "competition_end_date": competition_end_date,
        "results_label": results_label,
        "competition_year": competition_year,
    }
    return rows, relay_team_rows, relay_swimmer_rows, debug_df, stats, metadata



def parse_pdf(pdf_path: Path):
    pages = extract_text_lines(pdf_path)
    if any("Sistemas de Natação Swim It Up" in line for _, lines in pages[:2] for line in lines):
        return parse_brazil_pdf(pdf_path)
    if looks_like_hytek_two_column(pages):
        return parse_hytek_multicolumn_pdf(pdf_path, column_ranges=[(0, 300), (300, 620)])
    if looks_like_hytek_multicolumn(pages):
        return parse_hytek_multicolumn_pdf(pdf_path)
    stats = ParseStats(pages_read=len(pages))
    current_event: Optional[EventContext] = None
    current_combined_event: Optional[EventContext] = None
    combined_event_counter = 9000
    rows: List[ParsedResultRow] = []
    relay_team_rows: List[ParsedRelayTeamRow] = []
    relay_swimmer_rows: List[ParsedRelaySwimmerRow] = []
    debug_rows: List[Dict[str, Optional[str]]] = []
    last_relay_team_name: Optional[str] = None

    competition_name: Optional[str] = None
    results_label: Optional[str] = None
    competition_start_date: Optional[str] = None
    competition_end_date: Optional[str] = None
    competition_year: Optional[int] = None

    for page_number, lines in pages:
        for idx, raw_line in enumerate(lines, start=1):
            line = raw_line.strip()
            if not line:
                stats.lines_skipped += 1
                continue

            if competition_name is None:
                parsed_name, parsed_start_date, parsed_end_date = parse_competition_header(line)
                if parsed_name is not None:
                    competition_name = parsed_name
                    competition_start_date = parsed_start_date
                    competition_end_date = parsed_end_date
            if results_label is None and line.lower().startswith("results"):
                results_label = line

            if competition_year is None:
                meta_probe = {
                    "competition_start_date": competition_start_date,
                    "competition_end_date": competition_end_date,
                    "competition_name": competition_name,
                    "results_label": results_label,
                }
                competition_year = derive_competition_year(meta_probe, pdf_path)

            if should_skip_line(line):
                stats.lines_skipped += 1
                continue

            combined_event = parse_combined_event_header(line, combined_event_counter)
            if combined_event is not None:
                current_event = None
                current_combined_event = combined_event
                combined_event_counter += 1
                stats.event_headers_found += 4
                continue

            event = parse_event_header(line)
            if event is not None:
                current_event = event
                current_combined_event = None
                last_relay_team_name = None
                stats.event_headers_found += 1
                continue

            if line.startswith("(") and line.endswith(")"):
                inner = line[1:-1].strip()
                event = parse_event_header(inner)
                if event is not None:
                    current_event = event
                    current_combined_event = None
                    last_relay_team_name = None
                    stats.event_headers_found += 1
                    continue

            if current_combined_event is not None:
                combined_rows = parse_combined_result_line(line, current_combined_event, page_number, idx, competition_year)
                if combined_rows:
                    rows.extend(combined_rows)
                    stats.result_rows_found += len(combined_rows)
                    continue

                stats.lines_unparsed += 1
                debug_rows.append(
                    {
                        "page_number": page_number,
                        "line_number": idx,
                        "event_name_context": current_combined_event.event_name,
                        "raw_line": line,
                        "reason": "unparsed_combined_event_line",
                    }
                )
                continue

            if current_event is None:
                stats.lines_skipped += 1
                continue

            if current_event.is_relay:
                relay_team = parse_relay_team_line(line, current_event, page_number, idx)
                if relay_team is not None:
                    relay_team_rows.append(relay_team)
                    last_relay_team_name = relay_team.relay_team_name
                    stats.relay_team_rows_found += 1
                    continue

                relay_swimmers = parse_relay_swimmer_line(line, current_event, page_number, idx, last_relay_team_name, competition_year)
                if relay_swimmers:
                    relay_swimmer_rows.extend(relay_swimmers)
                    stats.relay_swimmer_rows_found += len(relay_swimmers)
                    continue

                stats.lines_unparsed += 1
                debug_rows.append(
                    {
                        "page_number": page_number,
                        "line_number": idx,
                        "event_name_context": current_event.event_name,
                        "raw_line": line,
                        "reason": "unparsed_relay_line",
                    }
                )
                continue

            parsed = parse_result_line(line, current_event, page_number, idx, competition_year)
            if parsed is not None:
                rows.append(parsed)
                stats.result_rows_found += 1
                continue

            stats.lines_unparsed += 1
            debug_rows.append(
                {
                    "page_number": page_number,
                    "line_number": idx,
                    "event_name_context": current_event.event_name,
                    "raw_line": line,
                    "reason": "unparsed_inside_event",
                }
            )

    reconcile_relay_swimmers_with_individuals(rows, relay_team_rows, relay_swimmer_rows)
    relay_team_rows, relay_swimmer_rows = deduplicate_relay_rows(relay_team_rows, relay_swimmer_rows)

    debug_df = pd.DataFrame(debug_rows, columns=["page_number", "line_number", "event_name_context", "raw_line", "reason"])
    metadata = {
        "pdf_name": pdf_path.name,
        "pdf_sha256": compute_file_sha256(pdf_path),
        "parser_version": PARSER_VERSION,
        "competition_name": competition_name,
        "competition_start_date": competition_start_date,
        "competition_end_date": competition_end_date,
        "results_label": results_label,
        "competition_year": competition_year,
    }
    return rows, relay_team_rows, relay_swimmer_rows, debug_df, stats, metadata



def build_output_frames(parsed_rows: List[ParsedResultRow], relay_team_rows: List[ParsedRelayTeamRow], relay_swimmer_rows: List[ParsedRelaySwimmerRow], competition_id: Optional[int], default_source_id: Optional[int], metadata: Dict[str, Optional[str]]) -> Dict[str, pd.DataFrame]:
    source_id_value = str(default_source_id) if default_source_id is not None else None
    competition_year = metadata.get("competition_year")

    event_records: List[Dict[str, Optional[str]]] = []
    athlete_records: List[Dict[str, Optional[str]]] = []
    result_records: List[Dict[str, Optional[str]]] = []
    club_records: List[Dict[str, Optional[str]]] = []
    relay_team_records: List[Dict[str, Optional[str]]] = []
    relay_swimmer_records: List[Dict[str, Optional[str]]] = []

    seen_clubs = set()
    seen_athletes = set()
    seen_events = set()

    def ensure_event(row_event_number: int, row_event_name: str):
        if row_event_name in seen_events:
            return
        seen_events.add(row_event_name)
        event_match = EVENT_HEADER_RE.match(f"Event {row_event_number} {row_event_name}")
        if not event_match:
            fail(f"No se pudo reconstruir metadata del evento: {row_event_name}")
        event_records.append(
            {
                "competition_id": str(competition_id) if competition_id is not None else None,
                "event_name": row_event_name,
                "stroke": normalize_stroke(event_match.group("stroke")),
                "distance_m": str(parse_distance_to_meters(event_match.group("distance_raw")) or 0),
                "gender": normalize_event_gender(event_match.group("gender")),
                "age_group": event_match.group("age_group").strip(),
                "round_type": "final",
                "source_id": source_id_value,
            }
        )

    for row in parsed_rows:
        club_key = normalize_controlled_lower(row.club_name)
        if club_key and club_key not in seen_clubs:
            seen_clubs.add(club_key)
            club_records.append({"name": row.club_name, "short_name": None, "city": None, "region": None, "source_id": source_id_value})

        ensure_event(row.event_number, row.event_name)

        athlete_key = (normalize_controlled_lower(row.athlete_name), club_key)
        if athlete_key not in seen_athletes:
            seen_athletes.add(athlete_key)
            event_match = EVENT_HEADER_RE.match(f"Event {row.event_number} {row.event_name}")
            athlete_records.append(
                {
                    "full_name": row.athlete_name,
                    "gender": normalize_athlete_gender(event_match.group("gender")) if event_match else None,
                    "club_name": row.club_name,
                    "birth_year": str(row.birth_year_estimated) if row.birth_year_estimated is not None else None,
                    "source_id": source_id_value,
                }
            )

        result_records.append(
            {
                "event_name": row.event_name,
                "athlete_name": row.athlete_name,
                "club_name": row.club_name,
                "rank_position": row.rank_position,
                "age_at_event": str(row.age_at_event) if row.age_at_event is not None else None,
                "birth_year_estimated": str(row.birth_year_estimated) if row.birth_year_estimated is not None else None,
                "seed_time_text": row.seed_time_text,
                "seed_time_ms": row.seed_time_ms,
                "result_time_text": row.result_time_text,
                "result_time_ms": row.result_time_ms,
                "points": row.points,
                "status": row.status,
                "source_id": source_id_value,
            }
        )

    for row in relay_team_rows:
        ensure_event(row.event_number, row.event_name)
        relay_team_records.append(
            {
                "event_name": row.event_name,
                "club_name": row.club_name,
                "relay_team_name": row.relay_team_name,
                "rank_position": row.rank_position,
                "seed_time_text": row.seed_time_text,
                "seed_time_ms": row.seed_time_ms,
                "result_time_text": row.result_time_text,
                "result_time_ms": row.result_time_ms,
                "points": row.points,
                "status": row.status,
                "source_id": source_id_value,
                "page_number": row.page_number,
                "line_number": row.line_number,
            }
        )

    for row in relay_swimmer_rows:
        relay_swimmer_records.append(
            {
                "event_name": row.event_name,
                "relay_team_name": row.relay_team_name,
                "leg_order": str(row.leg_order),
                "swimmer_name": row.swimmer_name,
                "gender": row.gender,
                "age_at_event": str(row.age_at_event) if row.age_at_event is not None else None,
                "birth_year_estimated": str(row.birth_year_estimated) if row.birth_year_estimated is not None else None,
                "page_number": row.page_number,
                "line_number": row.line_number,
            }
        )

    frames = {
        "club": pd.DataFrame(club_records, columns=["name", "short_name", "city", "region", "source_id"]),
        "event": pd.DataFrame(event_records, columns=["competition_id", "event_name", "stroke", "distance_m", "gender", "age_group", "round_type", "source_id"]),
        "athlete": pd.DataFrame(athlete_records, columns=["full_name", "gender", "club_name", "birth_year", "source_id"]),
        "result": pd.DataFrame(result_records, columns=["event_name", "athlete_name", "club_name", "rank_position", "age_at_event", "birth_year_estimated", "seed_time_text", "seed_time_ms", "result_time_text", "result_time_ms", "points", "status", "source_id"]),
        "raw_result": pd.DataFrame([asdict(r) for r in parsed_rows]),
        "relay_team": pd.DataFrame(relay_team_records, columns=["event_name", "club_name", "relay_team_name", "rank_position", "seed_time_text", "seed_time_ms", "result_time_text", "result_time_ms", "points", "status", "source_id", "page_number", "line_number"]),
        "relay_swimmer": pd.DataFrame(relay_swimmer_records, columns=["event_name", "relay_team_name", "leg_order", "swimmer_name", "gender", "age_at_event", "birth_year_estimated", "page_number", "line_number"]),
        "raw_relay_team": pd.DataFrame([asdict(r) for r in relay_team_rows]),
        "raw_relay_swimmer": pd.DataFrame([asdict(r) for r in relay_swimmer_rows]),
    }
    return frames



def save_outputs(frames: Dict[str, pd.DataFrame], debug_df: pd.DataFrame, metadata: Dict[str, Optional[str]], out_dir: Path, excel_name: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    for key, df in frames.items():
        csv_path = out_dir / f"{key}.csv"
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    debug_df.to_csv(out_dir / "debug_unparsed_lines.csv", index=False, encoding="utf-8-sig")

    workbook_path = out_dir / excel_name
    with pd.ExcelWriter(workbook_path, engine="openpyxl") as writer:
        for sheet_name in [
            "club", "event", "athlete", "result", "raw_result",
            "relay_team", "relay_swimmer", "raw_relay_team", "raw_relay_swimmer"
        ]:
            frames[sheet_name].to_excel(writer, sheet_name=sheet_name[:31], index=False)
        debug_df.to_excel(writer, sheet_name="debug_unparsed", index=False)

    with open(out_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extrae resultados desde un PDF estilo FCHMN a archivos intermedios CSV/XLSX listos para revisar."
    )
    parser.add_argument("--pdf", required=True, help="Ruta al PDF de resultados")
    parser.add_argument("--out-dir", required=True, help="Carpeta de salida para CSV/XLSX")
    parser.add_argument("--competition-id", type=int, help="competition_id opcional para poblar la hoja event")
    parser.add_argument("--default-source-id", type=int, help="source_id opcional para poblar hojas de salida")
    parser.add_argument("--excel-name", default="parsed_results.xlsx", help="Nombre del archivo Excel de salida")
    return parser.parse_args()



def main() -> None:
    args = parse_args()
    pdf_path = Path(args.pdf)
    out_dir = Path(args.out_dir)

    if not pdf_path.exists():
        fail(f"No existe el PDF: {pdf_path}")

    info(f"Leyendo PDF: {pdf_path}")
    parsed_rows, relay_team_rows, relay_swimmer_rows, debug_df, stats, metadata = parse_pdf(pdf_path)

    if not parsed_rows and not relay_team_rows:
        fail("No se extrajeron filas de resultados. Revisa el layout del PDF o el archivo de debug.")

    frames = build_output_frames(parsed_rows, relay_team_rows, relay_swimmer_rows, args.competition_id, args.default_source_id, metadata)
    save_outputs(frames, debug_df, metadata, out_dir, args.excel_name)

    print("\n=== RESUMEN DE EXTRACCIÓN ===")
    print(f"Páginas leídas:           {stats.pages_read}")
    print(f"Encabezados de evento:    {stats.event_headers_found}")
    print(f"Filas individuales:       {stats.result_rows_found}")
    print(f"Equipos de relevo:        {stats.relay_team_rows_found}")
    print(f"Nadadores de relevo:      {stats.relay_swimmer_rows_found}")
    print(f"Líneas omitidas:          {stats.lines_skipped}")
    print(f"Líneas no parseadas:      {stats.lines_unparsed}")
    print("---")
    print(f"club:                     {len(frames['club'])}")
    print(f"event:                    {len(frames['event'])}")
    print(f"athlete:                  {len(frames['athlete'])}")
    print(f"result:                   {len(frames['result'])}")
    print(f"raw_result:               {len(frames['raw_result'])}")
    print(f"relay_team:               {len(frames['relay_team'])}")
    print(f"relay_swimmer:            {len(frames['relay_swimmer'])}")
    print("\n[OK] Extracción terminada.")
    print(f"Salida: {out_dir}")

    if stats.lines_unparsed > 0:
        warn("Hay líneas no parseadas. Revisa debug_unparsed_lines.csv antes de cargar a staging.")


if __name__ == "__main__":
    main()
