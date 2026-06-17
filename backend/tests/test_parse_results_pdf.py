import hashlib
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = BACKEND_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import parse_results_pdf as parser
import run_pipeline_results as pipeline


FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "parser_golden_lines.json"


def load_fixture(name):
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))[name]


def individual_context():
    return parser.EventContext(
        event_number=1,
        gender="men",
        age_group="35-39",
        distance_label="100",
        distance_m=100,
        course_code="LC",
        stroke="freestyle",
    )


def relay_context():
    return parser.EventContext(
        event_number=2,
        gender="men",
        age_group="160-199",
        distance_label="4x50",
        distance_m=200,
        course_code="SC",
        stroke="freestyle_relay",
    )


def relay_women_context():
    return parser.EventContext(
        event_number=3,
        gender="women",
        age_group="240-279",
        distance_label="4x50",
        distance_m=200,
        course_code="SC",
        stroke="freestyle_relay",
    )


def relay_mixed_context():
    return parser.EventContext(
        event_number=4,
        gender="mixed",
        age_group="160-199",
        distance_label="4x50",
        distance_m=200,
        course_code="SC",
        stroke="freestyle_relay",
    )


def test_normalize_event_gender_to_competition_canon():
    assert parser.normalize_event_gender("Women") == "women"
    assert parser.normalize_event_gender("Hombres") == "men"
    assert parser.normalize_event_gender("Mixto") == "mixed"


def test_normalize_athlete_gender_to_person_canon():
    assert parser.normalize_athlete_gender("W") == "female"
    assert parser.normalize_athlete_gender("Mujer") == "female"
    assert parser.normalize_athlete_gender("M") == "male"


def test_normalize_stroke_to_domain_canon():
    assert parser.normalize_stroke("Libre") == "freestyle"
    assert parser.normalize_stroke("Espalda") == "backstroke"
    assert parser.normalize_stroke("Pecho") == "breaststroke"
    assert parser.normalize_stroke("Mariposa") == "butterfly"
    assert parser.normalize_stroke("Combinado") == "individual_medley"
    assert parser.normalize_stroke("Relevo Libre") == "freestyle_relay"
    assert parser.normalize_stroke("Relevo Combinado") == "medley_relay"
    assert parser.normalize_stroke("Breast 40 a 99 años") == "breaststroke"
    assert parser.normalize_stroke("Medley 120 a 159 años Relay") == "medley_relay"
    assert parser.normalize_stroke("Medley 280 y mas años Relay") == "medley_relay"
    assert parser.normalize_stroke("Medley Relay 280 y mas") == "medley_relay"
    assert parser.normalize_stroke("Medley Relay Pre Master") == "medley_relay"
    assert parser.normalize_stroke("CI Piscina Estadio") == "individual_medley"
    assert parser.normalize_stroke("CI Mayores de 50") == "individual_medley"


    assert parser.normalize_stroke("Estilo Libre Pre Master - Master") == "freestyle"


def test_should_skip_sudamericano_auxiliary_lines():
    assert parser.should_skip_line("==================================================================")
    assert parser.should_skip_line("Nombre Edad Equipo Sembrar Finales")
    assert parser.should_skip_line("SUDAMERICANO: 4:38.88")
    assert parser.should_skip_line("2024SUDAMERI: 9:51.01")
    assert parser.should_skip_line("1:16,69 2:43,68 (1:26,99) 4:11,76 (1:28,08)")
    assert not parser.should_skip_line("-- *Unda, Mariana 32 Tiburones Tolima 12:27.13 NS")


def test_competition_name_similarity_matches_planned_calendar_name():
    assert (
        pipeline.competition_name_similarity(
            "XIII Copa Penalolen Master Natacion 2026",
            "XIII Copa Peñalolén Máster",
        )
        >= pipeline.PLANNED_COMPETITION_MATCH_THRESHOLD
    )
    assert parser.normalize_stroke("4x50 Mts Combinado") == "medley_relay"


def test_choose_planned_competition_candidate_survives_calendar_date_change():
    candidate = pipeline.choose_planned_competition_candidate(
        "VII Copa Smart Swim Team",
        [
            (6, "VII Copa Smart Swim"),
            (7, "VI Copa Santiago Deporte"),
        ],
    )

    assert candidate is not None
    assert candidate[1:] == (6, "VII Copa Smart Swim")


def test_swim_time_normalization_and_milliseconds():
    assert parser.normalize_swim_time_text("35.40") == "35,40"
    assert parser.derive_result_time_ms("35.40") == 35400
    assert parser.normalize_swim_time_text("1:05.30") == "1:05,30"
    assert parser.derive_result_time_ms("1:05.30") == 65300
    assert parser.normalize_swim_time_text("1:02:03.45") == "62:03,45"
    assert parser.derive_result_time_ms("1:02:03.45") == 3723450
    assert parser.normalize_swim_time_text("DNS") == "DNS"
    assert parser.derive_result_time_ms("DNS") is None


def test_clean_athlete_name_removes_layout_artifacts_without_source_suffix():
    assert parser.clean_athlete_name("Fajardo |, Keytheen") == "Fajardo, Keytheen"
    assert parser.clean_athlete_name("Hermosilla1, Yasna") == "Hermosilla, Yasna"
    assert parser.clean_athlete_name("Rivas, Mª Del(cid:976)ina") == "Rivas, Maria Delfina"
    assert parser.clean_athlete_name("Rojas, 2") == "Rojas, 2"
    assert parser.clean_athlete_name("Garcíóa Cereceda, Alexis") == "García Cereceda, Alexis"
    assert parser.clean_athlete_name("Cantoó, Claudio") == "Canto, Claudio"
    assert parser.clean_athlete_name("Aguirre, Joseó Ignacio") == "Aguirre, José Ignacio"
    assert parser.clean_athlete_name("Bustos Araya, Maríóa Gabriela") == "Bustos Araya, María Gabriela"
    assert parser.clean_athlete_name("AÁlvarez, Alex") == "Álvarez, Alex"
    assert parser.clean_athlete_name("AÓvila Leal, Diego") == "Ávila Leal, Diego"
    assert parser.clean_athlete_name("Acuña Saóez, Heóctor") == "Acuña Sáez, Héctor"
    assert parser.clean_athlete_name("Cabello Tilleríéa, Andreés") == "Cabello Tillería, Andrés"
    assert parser.clean_athlete_name("Caro P, Cristoébal Fdo") == "Caro P, Cristóbal Fdo"
    assert parser.clean_athlete_name("Castañeda, Beleún") == "Castañeda, Belén"
    assert parser.clean_athlete_name("Alarcoán Carvajal, Cristiaán") == "Alarcón Carvajal, Cristián"
    assert parser.clean_athlete_name("Albornoz Ramíórez, Tania") == "Albornoz Ramírez, Tania"
    assert parser.clean_athlete_name("Bascuñaán, Matíás") == "Bascuñán, Matías"
    assert parser.clean_athlete_name("Contreras Saónchez, Jaime") == "Contreras Sánchez, Jaime"
    assert parser.clean_athlete_name("Gonzaélez, Andrés") == "González, Andrés"
    assert parser.clean_athlete_name("M e ñadier, Mauri ce") == "Menadier, Maurice"
    assert parser.clean_athlete_name("Muñ ñoz, Victor") == "Muñoz, Víctor"
    assert parser.clean_athlete_name("Olivares OÓ rdenes, Cristiaón") == "Olivares Órdenes, Cristián"
    assert parser.clean_athlete_name("Yañ ñez, Roberto") == "Yáñez, Roberto"
    assert parser.clean_athlete_name("Sebastiaón, Claudio") == "Sebastián, Claudio"
    assert parser.clean_athlete_name("Gonzaólez, Andrés") == "González, Andrés"
    assert parser.clean_athlete_name("Rodríóguez, Alexandra") == "Rodríguez, Alexandra"
    assert parser.clean_athlete_name("*Unda, Mariana") == "Unda, Mariana"


def test_compute_file_sha256():
    expected = hashlib.sha256(FIXTURE_PATH.read_bytes()).hexdigest()

    assert parser.compute_file_sha256(FIXTURE_PATH) == expected


def test_result_status_from_text_statuses():
    assert parser.normalize_result_status(None, "DNS") == "dns"
    assert parser.normalize_result_status(None, "DNF") == "dnf"
    assert parser.normalize_result_status(None, "DQ") == "dsq"
    assert parser.normalize_result_status(None, "NT") == "unknown"
    assert parser.normalize_result_status(None, "1:05.30") == "valid"
    assert parser.normalize_result_status(None, "X1:05.30") == "valid"
    assert parser.normalize_result_status(None, "XDQ") == "dsq"


def test_parse_event_header_in_english_and_spanish():
    english = parser.parse_event_header("Event 1 Women 35-39 100 LC Meter Free")
    spanish = parser.parse_event_header("Evento 2 Hombres 40-44 50 CP Metro Espalda")
    relay = parser.parse_event_header("Evento 3 Mixto 160-199 4x50 CP Metro Relevo Libre")
    age_suffix = parser.parse_event_header("Event 4 Women 40-44 100 SC Meter Breast 40 a 99 años")
    relay_age_suffix = parser.parse_event_header("Event 5 Mixed 120-159 200 LC Meter Medley 120 a 159 años Relay")
    relay_aggregate_age_suffix = parser.parse_event_header("Event 10 Women 400 SC Meter Freestyle Relay 240 a 279")
    relay_trailing_age = parser.parse_event_header("Event 7 Mixed 200 SC Meter Medley C 160 a 199 años Relay")
    relay_trailing_label = parser.parse_event_header("Event 11 Mixed 100 SC Meter 4x100 mts Libres PM Relay")
    spanish_relay_trailing_age = parser.parse_event_header("Evento 11 Mixto 200 CL Metro Combinado 120 a 159 años Relevo")
    sudamericano_mixed_relay = parser.parse_event_header("Evento 17 Mixed 72-99 4x50 SC Metros Combinado Relay")

    sudamericano = parser.parse_event_header("Evento 1 Damas 18-24 400 SC Metros Comb. Ind.")
    compact = parser.parse_event_header("#1 Women 18-24 100 Meter IM")
    ocr_spaced = parser.parse_event_header("E vento 5 Mujeres 25-29 50 CC Metro Estilo Libre Pre Master - Master")

    assert english.event_name == "women 35-39 100 LC Meter freestyle"
    assert spanish.event_name == "men 40-44 50 SC Meter backstroke"
    assert relay.gender == "mixed"
    assert relay.distance_m == 200
    assert relay.stroke == "freestyle_relay"
    assert age_suffix.event_name == "women 40-44 100 SC Meter breaststroke"
    assert relay_age_suffix.distance_m == 200
    assert relay_age_suffix.stroke == "medley_relay"
    assert relay_aggregate_age_suffix.age_group == "240 a 279"
    assert relay_aggregate_age_suffix.distance_m == 400
    assert relay_aggregate_age_suffix.stroke == "freestyle_relay"
    assert relay_trailing_age.age_group == "C 160 a 199 años"
    assert relay_trailing_age.stroke == "medley_relay"
    assert relay_trailing_label.age_group == "PM"
    assert relay_trailing_label.stroke == "freestyle_relay"
    assert spanish_relay_trailing_age.age_group == "120 a 159 años"
    assert spanish_relay_trailing_age.stroke == "medley_relay"
    assert sudamericano_mixed_relay.gender == "mixed"
    assert sudamericano_mixed_relay.age_group == "72-99"
    assert sudamericano_mixed_relay.distance_m == 200
    assert sudamericano_mixed_relay.stroke == "medley_relay"
    assert sudamericano.gender == "women"
    assert sudamericano.stroke == "individual_medley"
    assert compact.course_code == "SC"
    assert compact.stroke == "individual_medley"
    assert ocr_spaced.stroke == "freestyle"


def test_parse_combined_quadathlon_line_as_four_canon_events():
    ctx = parser.parse_combined_event_header("Mujeres 25-29 Quadathlon", event_number=9000)
    rows = parser.parse_combined_result_line(
        "1 Albornoz, Javiera 27 LOZAD 2:27,10 33,96 34,80 46,97 31,37",
        ctx,
        page_number=1,
        line_number=11,
        competition_year=2024,
    )

    assert [row.event_name for row in rows] == [
        "women 25-29 50 LC Meter butterfly",
        "women 25-29 50 LC Meter backstroke",
        "women 25-29 50 LC Meter breaststroke",
        "women 25-29 50 LC Meter freestyle",
    ]
    assert rows[0].athlete_name == "Albornoz, Javiera"
    assert rows[0].age_at_event == 27
    assert rows[0].birth_year_estimated == 1997
    assert rows[-1].result_time_text == "31,37"


def test_parse_combined_quadathlon_repairs_single_ocr_short_split_from_total():
    ctx = parser.parse_combined_event_header("Hombres 30-34 Quadathlon", event_number=9000)
    rows = parser.parse_combined_result_line(
        "17 Eduardo Carrasco GOURA 2'29'55 36'03 41'50 4'46 31'56",
        ctx,
        page_number=4,
        line_number=19,
        competition_year=2023,
    )

    assert [row.result_time_text for row in rows] == ["36,03", "41,50", "40,46", "31,56"]
    assert rows[2].result_time_ms == "40460"


def test_parse_brazil_event_header_and_age_group():
    individual = parser.parse_brazil_event_header("1ª PROVA - 400 METROS MEDLEY FEMININO (13/04/2026)")
    relay = parser.parse_brazil_event_header("35ª PROVA - REVEZAMENTO 4X50 METROS LIVRE MISTO (17/04/2026)")

    assert individual.event_number == 1
    assert individual.gender == "women"
    assert individual.distance_m == 400
    assert individual.stroke == "individual_medley"
    assert relay.gender == "mixed"
    assert relay.distance_label == "4x50"
    assert relay.distance_m == 200
    assert relay.stroke == "freestyle_relay"
    assert parser.parse_brazil_age_group("FAIXA: 25 + ----") == "25+"


def test_parse_brazil_result_row_from_columns():
    ctx = parser.with_event_age_group(
        parser.parse_brazil_event_header("1ª PROVA - 400 METROS MEDLEY FEMININO (13/04/2026)"),
        "30+",
    )
    words = [
        {"text": "2º", "x0": 63, "top": 10},
        {"text": "133322", "x0": 94, "top": 10},
        {"text": "ROSEMARY", "x0": 120, "top": 10},
        {"text": "BADUÑA", "x0": 165, "top": 10},
        {"text": "NÚÑEZ", "x0": 210, "top": 10},
        {"text": "MASTER", "x0": 316, "top": 10},
        {"text": "URUGUAY", "x0": 350, "top": 10},
        {"text": "5:56.03", "x0": 412, "top": 10},
        {"text": "0,00", "x0": 451, "top": 10},
    ]

    row = parser.parse_brazil_result_row(words, ctx, page_number=1, line_number=5)

    assert row.athlete_name == "ROSEMARY BADUÑA NÚÑEZ"
    assert row.club_name == "MASTER URUGUAY"
    assert row.result_time_text == "5:56,03"
    assert row.result_time_ms == "356030"
    assert row.points == "0,00"
    assert row.age_at_event is None


def test_parse_brazil_result_row_splits_time_attached_to_club_cell():
    ctx = parser.EventContext(
        event_number=10,
        gender="men",
        age_group="50+",
        distance_label="50",
        distance_m=50,
        course_code="SC",
        stroke="freestyle",
    )
    words = [
        {"text": "10Âº", "x0": 63, "top": 10},
        {"text": "114785", "x0": 94, "top": 10},
        {"text": "JUAN", "x0": 120, "top": 10},
        {"text": "CARLOS", "x0": 150, "top": 10},
        {"text": "DA", "x0": 190, "top": 10},
        {"text": "SILVA", "x0": 210, "top": 10},
        {"text": "YEGROS", "x0": 250, "top": 10},
        {"text": "CLUB", "x0": 316, "top": 10},
        {"text": "DEPORTIVO", "x0": 342, "top": 10},
        {"text": "DA", "x0": 382, "top": 10},
        {"text": "SILVA32.47", "x0": 395, "top": 10},
        {"text": "0,00", "x0": 451, "top": 10},
    ]

    row = parser.parse_brazil_result_row(words, ctx, page_number=38, line_number=86)

    assert row is not None
    assert row.club_name == "CLUB DEPORTIVO DA SILVA"
    assert row.result_time_text == "32,47"
    assert row.result_time_ms == "32470"
    assert row.status == "valid"


def test_parse_brazil_relay_swimmer_row_rejects_extra_legs():
    ctx = parser.with_event_age_group(
        parser.parse_brazil_event_header("35ª PROVA - REVEZAMENTO 4X50 METROS LIVRE MISTO (17/04/2026)"),
        "160+",
    )
    words = [
        {"text": "106557", "x0": 64, "x1": 105, "top": 10},
        {"text": "CARLA", "x0": 125, "x1": 160, "top": 10},
        {"text": "STEIN", "x0": 165, "x1": 200, "top": 10},
        {"text": "STURION", "x0": 205, "x1": 270, "top": 10},
    ]

    row = parser.parse_brazil_relay_swimmer_row(
        words,
        ctx,
        page_number=125,
        line_number=7,
        relay_team_name='TNT MASTERS SP "A"',
        leg_order=5,
    )

    assert row is None


def test_parse_brazil_relay_team_row_repairs_adaip_line_wrap():
    ctx = parser.EventContext(
        event_number=35,
        gender="men",
        age_group="120+",
        distance_label="4x50",
        distance_m=200,
        course_code="SC",
        stroke="freestyle_relay",
    )
    words = [
        {"text": "6Âº", "x0": 63, "top": 10},
        {"text": "ASSOCIAÇÃO", "x0": 125, "top": 10},
        {"text": "DE", "x0": 175, "top": 10},
        {"text": "DESPORTOS", "x0": 195, "top": 10},
        {"text": "AQUÁTICOS", "x0": 245, "top": 10},
        {"text": "DO", "x0": 298, "top": 10},
        {"text": "INTERIORADAIP", "x0": 316, "top": 10},
        {"text": "1:52.04", "x0": 414, "top": 10},
        {"text": "0,00", "x0": 451, "top": 10},
    ]

    row = parser.parse_brazil_relay_team_row(words, ctx, page_number=147, line_number=73)

    assert row is not None
    assert row.club_name == "ADAIP"
    assert row.relay_team_name == 'ASSOCIAÇÃO DE DESPORTOS AQUÁTICOS DO INTERIOR DE PE "A"'
    assert row.result_time_ms == "112040"


def test_clean_extracted_text_repairs_cid_976_in_club_names():
    assert parser.clean_extracted_text("Del(cid:976)ines LC") == "Delfines LC"


def test_parse_individual_result_line_with_seed_fixture():
    fixture = load_fixture("individual_with_seed")
    row = parser.parse_result_line(
        fixture["line"],
        individual_context(),
        page_number=1,
        line_number=10,
        competition_year=fixture["competition_year"],
    )

    assert row is not None
    assert row.athlete_name == "Juan Perez"
    assert row.club_name == "Club Deportivo"
    assert row.rank_position == "1"
    assert row.age_at_event == 35
    assert row.birth_year_estimated == 1991
    assert row.seed_time_text == "1:05,30"
    assert row.seed_time_ms == "65300"
    assert row.result_time_text == "1:03,21"
    assert row.result_time_ms == "63210"
    assert row.points == "9"
    assert row.status == "valid"


def test_parse_individual_result_line_without_seed_fixture():
    fixture = load_fixture("individual_without_seed")
    row = parser.parse_result_line(
        fixture["line"],
        individual_context(),
        page_number=1,
        line_number=11,
        competition_year=fixture["competition_year"],
    )

    assert row is not None
    assert row.athlete_name == "Maria Lopez"
    assert row.seed_time_text is None
    assert row.result_time_text == "35,40"
    assert row.result_time_ms == "35400"
    assert row.points is None


def test_parse_individual_result_line_reclassifies_points_as_points_not_final_time():
    row = parser.parse_result_line(
        "8 Morales, Alonso 29 Master Triton De Rufino 1:22,49 1,00",
        individual_context(),
        page_number=1,
        line_number=30,
        competition_year=2022,
    )

    assert row is not None
    assert row.seed_time_text is None
    assert row.result_time_text == "1:22,49"
    assert row.result_time_ms == "82490"
    assert row.points == "1,00"


def test_parse_individual_result_line_drops_spurious_seed_before_nt_seed():
    row = parser.parse_result_line(
        "10 Larghi, Stephanie 33 Orinoco Swim 23 NT 4:06,79",
        individual_context(),
        page_number=1,
        line_number=31,
        competition_year=2025,
    )

    assert row is not None
    assert row.club_name == "Orinoco Swim"
    assert row.seed_time_text == "NT"
    assert row.seed_time_ms is None
    assert row.result_time_text == "4:06,79"
    assert row.result_time_ms == "246790"


def test_parse_individual_result_line_shifts_spurious_seed_before_seed_and_final():
    row = parser.parse_result_line(
        "14 Pineda, Miguel 29 Orinoco Swim 23 41,00 40,35",
        individual_context(),
        page_number=1,
        line_number=32,
        competition_year=2025,
    )

    assert row is not None
    assert row.seed_time_text == "41,00"
    assert row.seed_time_ms == "41000"
    assert row.result_time_text == "40,35"
    assert row.result_time_ms == "40350"
    assert row.points is None


def test_parse_individual_result_line_shifts_spurious_seed_before_nt_and_final():
    row = parser.parse_result_line(
        "5 Veas, Danika 35 Orinoco Swim 23 NT 58,24",
        individual_context(),
        page_number=1,
        line_number=33,
        competition_year=2025,
    )

    assert row is not None
    assert row.club_name == "Orinoco Swim"
    assert row.seed_time_text == "NT"
    assert row.seed_time_ms is None
    assert row.result_time_text == "58,24"
    assert row.result_time_ms == "58240"
    assert row.points is None


def test_parse_individual_result_line_drops_dsq_trailing_time_as_points():
    row = parser.parse_result_line(
        "--- Jaitul, Anay 35 Club Natacion Araucania 1:20.00 DQ 58.80",
        individual_context(),
        page_number=1,
        line_number=37,
        competition_year=2023,
    )

    assert row is not None
    assert row.rank_position is None
    assert row.seed_time_text == "1:20,00"
    assert row.result_time_text == "DQ"
    assert row.status == "dsq"
    assert row.points is None


def test_parse_individual_result_line_drops_unranked_dsq_points():
    row = parser.parse_result_line(
        "--- Cuevas, Matias 28 Club Deportivo UC 1:21,22 DQ 9",
        individual_context(),
        page_number=17,
        line_number=46,
        competition_year=2024,
    )

    assert row is not None
    assert row.rank_position is None
    assert row.status == "dsq"
    assert row.points is None


def test_parse_individual_result_line_clears_implausible_seed_for_long_event():
    row = parser.parse_result_line(
        "4 Saavedra, Francisco 30 Goura Swim Team 11,30 1:17,58 5",
        individual_context(),
        page_number=1,
        line_number=33,
        competition_year=2023,
    )

    assert row is not None
    assert row.seed_time_text is None
    assert row.seed_time_ms is None
    assert row.result_time_text == "1:17,58"
    assert row.result_time_ms == "77580"


def test_parse_result_line_recovers_seed_time_before_status_result():
    row = parser.parse_result_line(
        "--- Cabrillana, Mariano 38 Club Sparta A C 49.33 DQ DQ",
        individual_context(),
        page_number=1,
        line_number=12,
        competition_year=2025,
    )

    assert row is not None
    assert row.club_name == "Club Sparta A C"
    assert row.seed_time_text == "49,33"
    assert row.seed_time_ms == "49330"
    assert row.result_time_text == "DQ"
    assert row.result_time_ms is None
    assert row.status == "dsq"


def test_parse_result_line_accepts_double_dash_unranked_status_result():
    row = parser.parse_result_line(
        "-- *Unda, Mariana 32 Tiburones Tolima 12:27.13 NS",
        individual_context(),
        page_number=1,
        line_number=12,
        competition_year=2022,
    )

    assert row is not None
    assert row.rank_position is None
    assert row.athlete_name == "Unda, Mariana"
    assert row.club_name == "Tiburones Tolima"
    assert row.seed_time_text == "12:27,13"
    assert row.result_time_text == "NS"
    assert row.status == "unknown"


def test_parse_fragmented_result_line_from_hytek_multicolumn_ocr():
    row = parser.parse_result_line(
        "4 D e l g a d o , Ar t u r o 3 8 S T G O D 1 : 1 6 , 4 3",
        individual_context(),
        page_number=1,
        line_number=40,
        competition_year=2023,
    )

    assert row is not None
    assert row.athlete_name == "Delgado, Arturo"
    assert row.age_at_event == 38
    assert row.club_name == "STGOD"
    assert row.result_time_text == "1:16,43"


def test_parse_result_line_recovers_duplicated_age_digit_before_club():
    row = parser.parse_result_line(
        "--- Rojas, 2 20 Escuela de Suboficiales del Ej NT X1:30,58",
        individual_context(),
        page_number=25,
        line_number=29,
        competition_year=2024,
    )

    assert row is not None
    assert row.athlete_name == "Rojas,"
    assert row.age_at_event == 20
    assert row.birth_year_estimated == 2004
    assert row.club_name == "Escuela de Suboficiales del Ej"
    assert row.result_time_text == "X1:30,58"
    assert row.result_time_ms == "90580"
    assert row.status == "valid"


def test_parse_result_line_keeps_single_digit_age_for_child_event():
    child_context = parser.EventContext(
        event_number=1,
        gender="men",
        age_group="9-10",
        distance_label="50",
        distance_m=50,
        course_code="LC",
        stroke="freestyle",
    )

    row = parser.parse_result_line(
        "1 Perez, Tomas 9 Escuela Infantil 45,12 44,90",
        child_context,
        page_number=1,
        line_number=3,
        competition_year=2026,
    )

    assert row is not None
    assert row.athlete_name == "Perez, Tomas"
    assert row.age_at_event == 9
    assert row.birth_year_estimated == 2017
    assert row.club_name == "Escuela Infantil"


def test_detects_hytek_two_column_layout():
    assert parser.looks_like_hytek_two_column(
        [
            (
                1,
                [
                    "Event 1 Women 18-24 200 LC Meter Butterfly Event 2 Women 45-49 50 LC Meter Breaststroke",
                ],
            )
        ]
    )


def test_parse_relay_team_line_fixture():
    fixture = load_fixture("relay_team")
    row = parser.parse_relay_team_line(
        fixture["line"],
        relay_context(),
        page_number=2,
        line_number=20,
    )

    assert row is not None
    assert row.relay_team_name == "Club Deportivo A"
    assert row.seed_time_text == "4:30,00"
    assert row.result_time_text == "4:22,50"
    assert row.result_time_ms == "262500"
    assert row.points == "18"


def test_parse_relay_team_line_reclassifies_points_as_points_not_final_time():
    row = parser.parse_relay_team_line(
        "2 Master del Ñielol 2:30,55 2,00",
        relay_context(),
        page_number=2,
        line_number=25,
    )

    assert row is not None
    assert row.seed_time_text is None
    assert row.result_time_text == "2:30,55"
    assert row.result_time_ms == "150550"
    assert row.points == "2,00"


def test_parse_relay_team_line_reclassifies_relay_points_as_points_not_final_time():
    row = parser.parse_relay_team_line(
        "1 Club Atr Valdivia A 2:00,32 18,00",
        relay_context(),
        page_number=1,
        line_number=15,
    )

    assert row is not None
    assert row.seed_time_text is None
    assert row.result_time_text == "2:00,32"
    assert row.result_time_ms == "120320"
    assert row.points == "18,00"


def test_parse_relay_team_line_drops_unranked_exhibition_points():
    row = parser.parse_relay_team_line(
        "--- Santiago Deporte A 2:15,00 X2:27,46 18",
        relay_context(),
        page_number=28,
        line_number=13,
    )

    assert row is not None
    assert row.rank_position is None
    assert row.result_time_text == "X2:27,46"
    assert row.status == "valid"
    assert row.points is None


def test_deduplicate_relay_rows_removes_same_relay_seen_on_multiple_pages():
    team = parser.parse_relay_team_line(
        "1 Club Atr Valdivia A 2:00,32 18,00",
        relay_context(),
        page_number=24,
        line_number=7,
    )
    duplicate_team = parser.parse_relay_team_line(
        "1 Club Atr Valdivia A 2:00,32 18,00",
        relay_context(),
        page_number=27,
        line_number=7,
    )
    swimmers = parser.parse_relay_swimmer_line(
        "1) Meza, Valentina W28 2) Jimenez, Karina W32 3) Vega, Ana W31 4) Vilches, Monserrat W28",
        relay_context(),
        page_number=24,
        line_number=8,
        relay_team_name="Club Atr Valdivia A",
        competition_year=2025,
    )
    duplicate_swimmers = parser.parse_relay_swimmer_line(
        "1) Meza, Valentina W28 2) Jimenez, Karina W32 3) Vega, Ana W31 4) Vilches, Monserrat W28",
        relay_context(),
        page_number=27,
        line_number=8,
        relay_team_name="Club Atr Valdivia A",
        competition_year=2025,
    )

    unique_teams, unique_swimmers = parser.deduplicate_relay_rows(
        [team, duplicate_team],
        swimmers + duplicate_swimmers,
    )

    assert len(unique_teams) == 1
    assert [row.leg_order for row in unique_swimmers] == [1, 2, 3, 4]


def test_parse_relay_swimmer_line_fixture():
    fixture = load_fixture("relay_swimmers")
    rows = parser.parse_relay_swimmer_line(
        fixture["line"],
        relay_context(),
        page_number=2,
        line_number=21,
        relay_team_name="Club Deportivo A",
        competition_year=fixture["competition_year"],
    )

    assert [row.leg_order for row in rows] == [1, 2, 3, 4]
    assert rows[0].swimmer_name == "Juan Perez"
    assert rows[0].gender == "male"
    assert rows[0].age_at_event == 35
    assert rows[0].birth_year_estimated == 1991


def test_parse_relay_swimmer_continuation_line_assigns_sequential_legs():
    rows = parser.parse_relay_swimmer_continuation_line(
        "Perez, Romulo M31 Correa, Carolina W31",
        relay_mixed_context(),
        page_number=4,
        line_number=30,
        relay_team_name="Ñuñoa A",
        competition_year=2023,
        starting_leg_order=1,
    )

    assert [row.leg_order for row in rows] == [1, 2]
    assert [row.swimmer_name for row in rows] == ["Perez, Romulo", "Correa, Carolina"]
    assert [row.gender for row in rows] == ["male", "female"]
    assert [row.birth_year_estimated for row in rows] == [1992, 1992]


def test_parse_relay_swimmer_continuation_line_ignores_rows_without_comma_names():
    rows = parser.parse_relay_swimmer_continuation_line(
        "1 Ñuñoa A 4:15,00",
        relay_mixed_context(),
        page_number=4,
        line_number=28,
        relay_team_name="Ñuñoa A",
        competition_year=2023,
        starting_leg_order=1,
    )

    assert rows == []


def test_parse_relay_swimmer_line_splits_embedded_next_marker_after_age():
    rows = parser.parse_relay_swimmer_line(
        "3) Chamorro M, Alejandra Leonor W340) Levrini, Aldo M42",
        relay_context(),
        page_number=4,
        line_number=10,
        relay_team_name="CDUC A",
        competition_year=2024,
    )

    assert [row.leg_order for row in rows] == [3, 4]
    assert rows[0].swimmer_name == "Chamorro M, Alejandra Leonor"
    assert rows[0].gender == "female"
    assert rows[0].age_at_event == 34
    assert rows[1].swimmer_name == "Levrini, Aldo"
    assert rows[1].gender == "male"
    assert rows[1].age_at_event == 42


def test_parse_relay_swimmer_line_splits_marker_deformed_with_extra_digit():
    rows = parser.parse_relay_swimmer_line(
        "1) Campos Carrasco, Alejandrina W26)0 Brain, Cynthia W60 3) Pasarin, Claudia W60 4) Valdivia, Adriana W61",
        relay_context(),
        page_number=5,
        line_number=38,
        relay_team_name="Peñalolen Master A",
        competition_year=2024,
    )

    assert [row.leg_order for row in rows] == [1, 2, 3, 4]
    assert rows[0].swimmer_name == "Campos Carrasco, Alejandrina"
    assert rows[0].age_at_event == 26
    assert rows[1].swimmer_name == "Brain, Cynthia"
    assert rows[1].age_at_event == 60


def test_parse_relay_swimmer_line_splits_marker_embedded_after_name():
    rows = parser.parse_relay_swimmer_line(
        "1) Carvajal Illanes, Avelina W66 2) Schwarzemberg, Maríáa Angeálica3 W) P6a8saríán, Claudia W59 4) Valdivia, Adriana W60",
        relay_women_context(),
        page_number=5,
        line_number=8,
        relay_team_name="Peñalolen Master B",
        competition_year=2023,
    )

    assert [row.leg_order for row in rows] == [1, 2, 3, 4]
    assert rows[1].swimmer_name == "Schwarzemberg, María Angélica"
    assert rows[2].swimmer_name == "P6a8saríán, Claudia"
    assert rows[2].age_at_event == 59


def test_reconcile_relay_swimmers_uses_digitless_name_with_age_evidence():
    relay_team = parser.ParsedRelayTeamRow(
        page_number=5,
        line_number=7,
        event_number=3,
        event_name=relay_women_context().event_name,
        relay_team_name="Peñalolen Master B",
        club_name="Peñalolen Master",
        rank_position="1",
        seed_time_text=None,
        seed_time_ms=None,
        result_time_text="2:30,00",
        result_time_ms="150000",
        status="valid",
        points=None,
        raw_line="1 Peñalolen Master B 2:30,00",
    )
    individual_rows = [
        parser.ParsedResultRow(
            page_number=1,
            line_number=1,
            event_number=1,
            event_name="women 65-69 50 SC Meter freestyle",
            athlete_name="Schwarzemberg, Maríá Angeálica",
            age_at_event=68,
            birth_year_estimated=1955,
            club_name="Peñalolen Master",
            rank_position="1",
            seed_time_text=None,
            seed_time_ms=None,
            result_time_text="40,00",
            result_time_ms="40000",
            status="valid",
            points=None,
            raw_line="",
        ),
        parser.ParsedResultRow(
            page_number=1,
            line_number=2,
            event_number=1,
            event_name="women 55-59 50 SC Meter freestyle",
            athlete_name="Pasaríán, Claudia",
            age_at_event=59,
            birth_year_estimated=1964,
            club_name="Peñalolen Master",
            rank_position="1",
            seed_time_text=None,
            seed_time_ms=None,
            result_time_text="41,00",
            result_time_ms="41000",
            status="valid",
            points=None,
            raw_line="",
        ),
    ]
    relay_swimmers = parser.parse_relay_swimmer_line(
        "1) Carvajal Illanes, Avelina W66 2) Schwarzemberg, Maríáa Angeálica3 W) P6a8saríán, Claudia W59 4) Valdivia, Adriana W60",
        relay_women_context(),
        page_number=5,
        line_number=8,
        relay_team_name="Peñalolen Master B",
        competition_year=2023,
    )

    parser.reconcile_relay_swimmers_with_individuals(individual_rows, [relay_team], relay_swimmers)

    assert relay_swimmers[1].swimmer_name == "Schwarzemberg, Maríá Angeálica"
    assert relay_swimmers[1].age_at_event == 68
    assert relay_swimmers[2].swimmer_name == "Pasaríán, Claudia"
    assert relay_swimmers[2].age_at_event == 59


def test_reconcile_relay_swimmers_infers_missing_gender_in_mixed_relay_from_individuals():
    relay_team = parser.ParsedRelayTeamRow(
        page_number=1,
        line_number=10,
        event_number=relay_mixed_context().event_number,
        event_name=relay_mixed_context().event_name,
        relay_team_name="Peñalolen Master A",
        club_name="Peñalolen Master",
        rank_position="1",
        seed_time_text=None,
        seed_time_ms=None,
        result_time_text="2:10,00",
        result_time_ms="130000",
        status="valid",
        points=None,
        raw_line="1 Peñalolen Master A 2:10.00",
    )
    individual_rows = [
        parser.ParsedResultRow(
            page_number=1,
            line_number=1,
            event_number=11,
            event_name="women 40-44 50 SC Meter freestyle",
            athlete_name="Pinto Galleguillos, Rosario Soledad",
            age_at_event=42,
            birth_year_estimated=1982,
            club_name="Peñalolen Master",
            rank_position="1",
            seed_time_text=None,
            seed_time_ms=None,
            result_time_text="32,00",
            result_time_ms="32000",
            status="valid",
            points=None,
            raw_line="1 Pinto Galleguillos, Rosario Soledad 42 Peñalolen Master 32.00",
        ),
        parser.ParsedResultRow(
            page_number=1,
            line_number=2,
            event_number=12,
            event_name="men 45-49 50 SC Meter freestyle",
            athlete_name="Rojas, Juan",
            age_at_event=45,
            birth_year_estimated=1979,
            club_name="Peñalolen Master",
            rank_position="1",
            seed_time_text=None,
            seed_time_ms=None,
            result_time_text="30,00",
            result_time_ms="30000",
            status="valid",
            points=None,
            raw_line="1 Rojas, Juan 45 Peñalolen Master 30.00",
        ),
    ]

    relay_swimmers = parser.parse_relay_swimmer_line(
        "1) Pinto Galleguillos, Rosario Soledad 42 2) Rojas, Juan M45",
        relay_mixed_context(),
        page_number=2,
        line_number=20,
        relay_team_name="Peñalolen Master A",
        competition_year=2024,
    )

    assert relay_swimmers[0].gender == "mixed"

    parser.reconcile_relay_swimmers_with_individuals(individual_rows, [relay_team], relay_swimmers)

    assert relay_swimmers[0].swimmer_name == "Pinto Galleguillos, Rosario Soledad"
    assert relay_swimmers[0].gender == "female"
    assert relay_swimmers[0].age_at_event == 42
    assert relay_swimmers[0].birth_year_estimated == 1982


def test_parse_relay_swimmer_line_recovers_leg_marker_inside_age():
    rows = parser.parse_relay_swimmer_line(
        "1) Muñoz, Maria Olga W69 2) Ferrando, Nestor Alberto Domi M3)8 M3 aimone, Nicolasa W35 4) Le Cerf, Patricio M35",
        relay_context(),
        page_number=6,
        line_number=51,
        relay_team_name="Orinocoswim23 A",
        competition_year=2025,
    )

    assert [row.leg_order for row in rows] == [1, 2, 3, 4]
    assert rows[1].swimmer_name == "Ferrando, Nestor Alberto Domi"
    assert rows[1].age_at_event == 38
    assert rows[2].swimmer_name == "Maimone, Nicolasa"
    assert rows[2].age_at_event == 35


def test_build_output_frames_from_minimal_parsed_rows():
    individual_fixture = load_fixture("individual_with_seed")
    relay_team_fixture = load_fixture("relay_team")
    relay_swimmer_fixture = load_fixture("relay_swimmers")

    individual = parser.parse_result_line(
        individual_fixture["line"],
        individual_context(),
        page_number=1,
        line_number=10,
        competition_year=individual_fixture["competition_year"],
    )
    relay_team = parser.parse_relay_team_line(
        relay_team_fixture["line"],
        relay_context(),
        page_number=2,
        line_number=20,
    )
    relay_swimmers = parser.parse_relay_swimmer_line(
        relay_swimmer_fixture["line"],
        relay_context(),
        page_number=2,
        line_number=21,
        relay_team_name="Club Deportivo A",
        competition_year=relay_swimmer_fixture["competition_year"],
    )

    frames = parser.build_output_frames(
        parsed_rows=[individual],
        relay_team_rows=[relay_team],
        relay_swimmer_rows=relay_swimmers,
        competition_id=99,
        default_source_id=1,
        metadata={"competition_year": 2026},
    )

    assert set(frames) == {
        "club",
        "event",
        "athlete",
        "result",
        "raw_result",
        "relay_team",
        "relay_swimmer",
        "raw_relay_team",
        "raw_relay_swimmer",
    }
    assert frames["club"].to_dict("records") == [
        {"name": "Club Deportivo", "short_name": None, "city": None, "region": None, "source_id": "1"}
    ]
    assert frames["event"]["event_name"].tolist() == [
        "men 35-39 100 LC Meter freestyle",
        "men 160-199 4x50 SC Meter freestyle_relay",
    ]
    assert frames["result"].iloc[0].to_dict() == {
        "event_name": "men 35-39 100 LC Meter freestyle",
        "athlete_name": "Juan Perez",
        "club_name": "Club Deportivo",
        "rank_position": "1",
        "age_at_event": "35",
        "birth_year_estimated": "1991",
        "seed_time_text": "1:05,30",
        "seed_time_ms": "65300",
        "result_time_text": "1:03,21",
        "result_time_ms": "63210",
        "points": "9",
        "status": "valid",
        "source_id": "1",
    }
    assert frames["relay_team"].iloc[0]["relay_team_name"] == "Club Deportivo A"
    assert frames["relay_swimmer"]["leg_order"].tolist() == ["1", "2", "3", "4"]
