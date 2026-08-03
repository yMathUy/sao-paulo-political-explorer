import csv
import io
import unicodedata
import zipfile
from datetime import datetime

import requests


def candidate_archive_url(year):
    return (
        "https://cdn.tse.jus.br/estatistica/sead/odsele/"
        f"consulta_cand/consulta_cand_{year}.zip"
    )


def candidate_dataset_url(year):
    return (
        "https://dadosabertos.tse.jus.br/dataset/"
        f"candidatos-{year}"
    )


TSE_CANDIDATES_URL = candidate_archive_url(2024)
TSE_DATASET_URL = candidate_dataset_url(2024)


class TSECandidatesError(Exception):
    """Raised when official TSE candidate data cannot be loaded."""


def normalize_place_name(value):
    normalized = unicodedata.normalize("NFKD", value or "")
    return "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    ).casefold().strip()


def _parse_date(value):
    try:
        return datetime.strptime(value, "%d/%m/%Y").date()
    except (TypeError, ValueError):
        return None


def _clean_optional(value):
    if not value or value.startswith("#"):
        return ""
    return value


def parse_elected_municipal_officeholders(rows):
    """Return the latest elected mayor and vice-mayor per municipality."""
    selected = {}

    for row in rows:
        if row.get("SG_UF") != "SP":
            continue

        role = {
            "prefeito": "MAYOR",
            "vice-prefeito": "VICE_MAYOR",
        }.get(normalize_place_name(row.get("DS_CARGO")))
        if not role:
            continue

        status = normalize_place_name(row.get("DS_SIT_TOT_TURNO"))
        if status != "eleito":
            continue

        election_date = _parse_date(row.get("DT_ELEICAO"))
        if not election_date:
            continue

        municipality_key = normalize_place_name(row.get("NM_UE"))
        selection_key = (municipality_key, role)
        election_round = int(row.get("NR_TURNO") or 1)
        sort_key = (election_date, election_round)
        current = selected.get(selection_key)

        if current and current["_sort_key"] >= sort_key:
            continue

        selected[selection_key] = {
            "_sort_key": sort_key,
            "municipality_key": municipality_key,
            "municipality_name": row.get("NM_UE", "").title(),
            "role": role,
            "tse_candidate_id": int(row["SQ_CANDIDATO"]),
            "tse_municipality_code": row.get("SG_UE", ""),
            "name": row.get("NM_CANDIDATO", "").title(),
            "ballot_name": row.get("NM_URNA_CANDIDATO", "").title(),
            "social_name": _clean_optional(
                row.get("NM_SOCIAL_CANDIDATO", "")
            ).title(),
            "party": row.get("SG_PARTIDO", ""),
            "party_name": row.get("NM_PARTIDO", "").title(),
            "coalition_name": _clean_optional(
                row.get("NM_COLIGACAO", "")
            ).title(),
            "coalition_composition": _clean_optional(
                row.get("DS_COMPOSICAO_COLIGACAO", "")
            ),
            "birth_date": _parse_date(row.get("DT_NASCIMENTO")),
            "birth_state": _clean_optional(
                row.get("SG_UF_NASCIMENTO", "")
            ),
            "gender": row.get("DS_GENERO", "").title(),
            "education": row.get("DS_GRAU_INSTRUCAO", "").title(),
            "marital_status": row.get(
                "DS_ESTADO_CIVIL", ""
            ).title(),
            "race": row.get("DS_COR_RACA", "").title(),
            "occupation": row.get("DS_OCUPACAO", "").title(),
            "election_date": election_date,
            "election_type": row.get("NM_TIPO_ELEICAO", "").title(),
            "election_round": election_round,
            "electoral_status": row.get(
                "DS_SIT_TOT_TURNO", ""
            ).title(),
            "source_url": TSE_DATASET_URL,
        }

    for record in selected.values():
        record.pop("_sort_key", None)

    return list(selected.values())


def parse_sao_paulo_candidates(rows):
    candidates = []

    for row in rows:
        if row.get("SG_UF") != "SP":
            continue

        election_date = _parse_date(row.get("DT_ELEICAO"))
        candidate_id = row.get("SQ_CANDIDATO")
        if not election_date or not candidate_id:
            continue

        election_year = int(row.get("ANO_ELEICAO") or 0)
        candidates.append(
            {
                "tse_candidate_id": int(candidate_id),
                "municipality_key": normalize_place_name(
                    row.get("NM_UE")
                ),
                "tse_municipality_code": row.get("SG_UE", ""),
                "election_year": election_year,
                "election_date": election_date,
                "election_type": row.get(
                    "NM_TIPO_ELEICAO", ""
                ).title(),
                "election_description": row.get(
                    "DS_ELEICAO", ""
                ).title(),
                "election_scope": row.get(
                    "TP_ABRANGENCIA", ""
                ).title(),
                "election_round": int(row.get("NR_TURNO") or 1),
                "office": row.get("DS_CARGO", "").title(),
                "candidate_number": int(
                    row.get("NR_CANDIDATO") or 0
                ),
                "name": row.get("NM_CANDIDATO", "").title(),
                "ballot_name": row.get(
                    "NM_URNA_CANDIDATO", ""
                ).title(),
                "social_name": _clean_optional(
                    row.get("NM_SOCIAL_CANDIDATO", "")
                ).title(),
                "party": row.get("SG_PARTIDO", ""),
                "party_name": row.get("NM_PARTIDO", "").title(),
                "federation_name": _clean_optional(
                    row.get("NM_FEDERACAO", "")
                ).title(),
                "federation_composition": _clean_optional(
                    row.get("DS_COMPOSICAO_FEDERACAO", "")
                ),
                "coalition_name": _clean_optional(
                    row.get("NM_COLIGACAO", "")
                ).title(),
                "coalition_composition": _clean_optional(
                    row.get("DS_COMPOSICAO_COLIGACAO", "")
                ),
                "birth_date": _parse_date(row.get("DT_NASCIMENTO")),
                "birth_state": _clean_optional(
                    row.get("SG_UF_NASCIMENTO", "")
                ),
                "gender": row.get("DS_GENERO", "").title(),
                "education": row.get(
                    "DS_GRAU_INSTRUCAO", ""
                ).title(),
                "marital_status": row.get(
                    "DS_ESTADO_CIVIL", ""
                ).title(),
                "race": row.get("DS_COR_RACA", "").title(),
                "occupation": row.get("DS_OCUPACAO", "").title(),
                "candidacy_status": _clean_optional(
                    row.get("DS_SITUACAO_CANDIDATURA", "")
                ).title(),
                "result_status": _clean_optional(
                    row.get("DS_SIT_TOT_TURNO", "")
                ).title(),
                "source_url": candidate_dataset_url(election_year),
            }
        )

    return candidates


def _get_sp_rows(timeout, year=2024):
    response = requests.get(
        candidate_archive_url(year),
        timeout=timeout,
    )
    response.raise_for_status()

    archive = zipfile.ZipFile(io.BytesIO(response.content))
    filename = next(
        name
        for name in archive.namelist()
        if name.endswith("_SP.csv")
    )
    source = archive.open(filename)
    text_stream = io.TextIOWrapper(
        source,
        encoding="cp1252",
        newline="",
    )
    return archive, text_stream, csv.DictReader(text_stream, delimiter=";")


def get_elected_municipal_officeholders(timeout=90):
    try:
        archive, text_stream, rows = _get_sp_rows(timeout, 2024)
        with archive, text_stream:
            return parse_elected_municipal_officeholders(rows)
    except (
        requests.RequestException,
        zipfile.BadZipFile,
        StopIteration,
        OSError,
    ) as error:
        raise TSECandidatesError(
            "Could not load the official TSE candidate dataset."
        ) from error


def get_sao_paulo_candidates(year, timeout=90):
    try:
        archive, text_stream, rows = _get_sp_rows(timeout, year)
        with archive, text_stream:
            return parse_sao_paulo_candidates(rows)
    except (
        requests.RequestException,
        zipfile.BadZipFile,
        StopIteration,
        OSError,
    ) as error:
        raise TSECandidatesError(
            "Could not load the official TSE candidate dataset."
        ) from error
