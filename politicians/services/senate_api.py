from typing import Any

import requests
from django.core.cache import cache


SENATE_API_URL = "https://legis.senado.leg.br/dadosabertos"

SENATORS_CACHE_KEY = "current_sao_paulo_senators"
SENATORS_CACHE_TIMEOUT = 60 * 30

REQUEST_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "SaoPauloPoliticalExplorer/1.0",
}


class SenateAPIError(Exception):
    """Raised when data cannot be retrieved from the Senate API."""


def force_https(url: str | None) -> str:
    """Convert official HTTP links to HTTPS."""

    if not url:
        return ""

    return url.replace("http://", "https://", 1)


def as_list(value: Any) -> list[Any]:
    """Normalize an API field that may be an object or a list."""

    if isinstance(value, list):
        return value

    if isinstance(value, dict):
        return [value]

    return []


def parse_senator_mandates(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert the Senate mandate response into template-ready records."""

    raw_mandates = (
        payload
        .get("MandatoParlamentar", {})
        .get("Parlamentar", {})
        .get("Mandatos", {})
        .get("Mandato", [])
    )

    mandates = []

    for raw_mandate in as_list(raw_mandates):
        first_term = raw_mandate.get(
            "PrimeiraLegislaturaDoMandato",
            {},
        )
        second_term = raw_mandate.get(
            "SegundaLegislaturaDoMandato",
            {},
        )
        raw_parties = (
            raw_mandate
            .get("Partidos", {})
            .get("Partido", [])
        )
        parties = as_list(raw_parties)
        latest_party = parties[-1] if parties else {}

        substitutes = [
            {
                "id": substitute.get("CodigoParlamentar", ""),
                "name": substitute.get(
                    "NomeParlamentar",
                    "Name not available",
                ),
                "position": substitute.get(
                    "DescricaoParticipacao",
                    "Substitute",
                ),
            }
            for substitute in as_list(
                raw_mandate
                .get("Suplentes", {})
                .get("Suplente", [])
            )
        ]

        mandates.append(
            {
                "id": raw_mandate.get("CodigoMandato", ""),
                "state": raw_mandate.get("UfParlamentar", ""),
                "participation": raw_mandate.get(
                    "DescricaoParticipacao",
                    "",
                ),
                "start_date": first_term.get("DataInicio", ""),
                "end_date": (
                    second_term.get("DataFim")
                    or first_term.get("DataFim")
                    or ""
                ),
                "first_legislature": first_term.get(
                    "NumeroLegislatura",
                    "",
                ),
                "second_legislature": second_term.get(
                    "NumeroLegislatura",
                    "",
                ),
                "party": latest_party.get("Sigla", ""),
                "party_name": latest_party.get("Nome", ""),
                "substitutes": substitutes,
            }
        )

    mandates.sort(
        key=lambda mandate: mandate.get("start_date", ""),
        reverse=True,
    )

    return mandates


def parse_senator_committees(
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    """Convert Senate committee memberships into normalized records."""

    raw_committees = (
        payload
        .get("MembroComissaoParlamentar", {})
        .get("Parlamentar", {})
        .get("MembroComissoes", {})
        .get("Comissao", [])
    )
    committees = []

    for raw_committee in as_list(raw_committees):
        identification = raw_committee.get(
            "IdentificacaoComissao",
            {},
        )
        end_date = raw_committee.get("DataFim", "")

        committees.append(
            {
                "id": identification.get("CodigoComissao", ""),
                "abbreviation": identification.get(
                    "SiglaComissao",
                    "",
                ),
                "name": identification.get(
                    "NomeComissao",
                    "Name not available",
                ),
                "house": identification.get(
                    "SiglaCasaComissao",
                    "",
                ),
                "participation": raw_committee.get(
                    "DescricaoParticipacao",
                    "",
                ),
                "start_date": raw_committee.get("DataInicio", ""),
                "end_date": end_date,
                "is_current": not bool(end_date),
            }
        )

    committees.sort(
        key=lambda committee: (
            not committee["is_current"],
            committee.get("name", "").casefold(),
            committee.get("start_date", ""),
        )
    )

    return committees


def parse_senator_authorships(
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    """Convert Senate authorship records into normalized propositions."""

    raw_authorships = (
        payload
        .get("MateriasAutoriaParlamentar", {})
        .get("Parlamentar", {})
        .get("Autorias", {})
        .get("Autoria", [])
    )
    propositions = []

    for raw_authorship in as_list(raw_authorships):
        matter = raw_authorship.get("Materia", {})
        matter_id = matter.get("Codigo", "")
        is_primary_author = (
            str(
                raw_authorship.get(
                    "IndicadorAutorPrincipal",
                    "",
                )
            ).strip().casefold()
            in {"sim", "s", "yes", "true", "1"}
        )

        propositions.append(
            {
                "id": matter_id,
                "process_id": matter.get(
                    "IdentificacaoProcesso",
                    "",
                ),
                "description": matter.get(
                    "DescricaoIdentificacao",
                    "",
                ),
                "type": matter.get("Sigla", ""),
                "number": matter.get("Numero", ""),
                "year": matter.get("Ano", ""),
                "summary": matter.get("Ementa", ""),
                "date": matter.get("Data", ""),
                "is_primary_author": is_primary_author,
                "authorship_label": (
                    "Primary author"
                    if is_primary_author
                    else "Coauthor or signatory"
                ),
                "official_url": (
                    "https://www25.senado.leg.br/web/atividade/"
                    f"materias/-/materia/{matter_id}"
                    if matter_id
                    else ""
                ),
            }
        )

    propositions.sort(
        key=lambda proposition: (
            proposition.get("date", ""),
            proposition.get("id", ""),
        ),
        reverse=True,
    )

    return propositions


def parse_senator_votes(
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    """Convert Senate nominal voting records into normalized values."""

    raw_votes = (
        payload
        .get("VotacaoParlamentar", {})
        .get("Parlamentar", {})
        .get("Votacoes", {})
        .get("Votacao", [])
    )
    votes = []

    for raw_vote in as_list(raw_votes):
        session = raw_vote.get("SessaoPlenaria", {})
        matter = raw_vote.get("Materia", {})
        matter_id = matter.get("Codigo", "")
        session_date = session.get("DataSessao", "")

        votes.append(
            {
                "id": raw_vote.get(
                    "CodigoSessaoVotacao",
                    "",
                ),
                "sequence": raw_vote.get("Sequencial", ""),
                "session_id": session.get("CodigoSessao", ""),
                "session_number": session.get("NumeroSessao", ""),
                "session_type": session.get(
                    "SiglaTipoSessao",
                    "",
                ),
                "session_date": session_date,
                "session_year": (
                    session_date[:4]
                    if isinstance(session_date, str)
                    else ""
                ),
                "matter_id": matter_id,
                "matter": matter.get(
                    "DescricaoIdentificacao",
                    "",
                ),
                "matter_summary": matter.get("Ementa", ""),
                "description": raw_vote.get(
                    "DescricaoVotacao",
                    "",
                ),
                "result": raw_vote.get(
                    "DescricaoResultado",
                    "",
                ),
                "vote": (
                    raw_vote.get("DescricaoVoto")
                    or raw_vote.get("SiglaDescricaoVoto")
                    or "Not informed"
                ),
                "is_secret": (
                    str(
                        raw_vote.get(
                            "IndicadorVotacaoSecreta",
                            "",
                        )
                    ).strip().casefold()
                    in {"sim", "s", "yes", "true", "1"}
                ),
                "official_url": (
                    "https://www25.senado.leg.br/web/atividade/"
                    f"materias/-/materia/{matter_id}"
                    if matter_id
                    else ""
                ),
            }
        )

    votes.sort(
        key=lambda vote: (
            vote.get("session_date", ""),
            vote.get("id", ""),
            vote.get("sequence", ""),
        ),
        reverse=True,
    )

    return votes


def get_current_sao_paulo_senators() -> list[dict[str, Any]]:
    """Return senators currently serving for São Paulo."""

    cached_senators = cache.get(SENATORS_CACHE_KEY)

    if cached_senators is not None:
        return cached_senators

    try:
        response = requests.get(
            f"{SENATE_API_URL}/senador/lista/atual",
            headers=REQUEST_HEADERS,
            timeout=(3.05, 20),
        )

        response.raise_for_status()
        payload = response.json()

    except (requests.RequestException, ValueError) as error:
        raise SenateAPIError(
            "Senate data is temporarily unavailable."
        ) from error

    parliamentarians = (
        payload
        .get("ListaParlamentarEmExercicio", {})
        .get("Parlamentares", {})
        .get("Parlamentar", [])
    )

    if isinstance(parliamentarians, dict):
        parliamentarians = [parliamentarians]

    senators = []

    for parliamentarian in parliamentarians:
        identification = parliamentarian.get(
            "IdentificacaoParlamentar",
            {},
        )

        mandate = parliamentarian.get("Mandato", {})

        state = (
            mandate.get("UfParlamentar")
            or identification.get("UfParlamentar")
            or ""
        )

        if state.upper() != "SP":
            continue

        senator_id = identification.get("CodigoParlamentar")

        if not senator_id:
            continue

        senators.append(
            {
                "id": senator_id,
                "name": identification.get(
                    "NomeParlamentar",
                    "Name not available",
                ),
                "civil_name": identification.get(
                    "NomeCompletoParlamentar",
                    "",
                ),
                "party": identification.get(
                    "SiglaPartidoParlamentar",
                    "",
                ),
                "state": state.upper(),
                "photo_url": force_https(
                    identification.get("UrlFotoParlamentar")
                ),
                "profile_url": force_https(
                    identification.get("UrlPaginaParlamentar")
                ),
                "email": identification.get(
                    "EmailParlamentar",
                    "",
                ),
            }
        )

    senators.sort(
        key=lambda senator: senator.get("name", "").casefold()
    )

    cache.set(
        SENATORS_CACHE_KEY,
        senators,
        SENATORS_CACHE_TIMEOUT,
    )

    return senators


def get_senator_by_id(senator_id: int) -> dict[str, Any]:
    """Return detailed information about a senator."""

    cache_key = f"senator_{senator_id}"

    cached_senator = cache.get(cache_key)

    if cached_senator is not None:
        return cached_senator

    try:
        response = requests.get(
            f"{SENATE_API_URL}/senador/{senator_id}",
            headers=REQUEST_HEADERS,
            timeout=(3.05, 20),
        )

        response.raise_for_status()
        payload = response.json()

    except (requests.RequestException, ValueError) as error:
        raise SenateAPIError(
            "The senator profile is temporarily unavailable."
        ) from error

    details = payload.get("DetalheParlamentar", {})
    parliamentarian = details.get("Parlamentar", details)

    identification = parliamentarian.get(
        "IdentificacaoParlamentar",
        {},
    )

    basic_data = parliamentarian.get(
        "DadosBasicosParlamentar",
        {},
    )

    mandate = (
        parliamentarian.get("MandatoAtual")
        or parliamentarian.get("Mandato")
        or {}
    )

    senator = {
        "id": (
            identification.get("CodigoParlamentar")
            or senator_id
        ),
        "name": identification.get(
            "NomeParlamentar",
            "Name not available",
        ),
        "civil_name": identification.get(
            "NomeCompletoParlamentar",
            "",
        ),
        "party": identification.get(
            "SiglaPartidoParlamentar",
            "",
        ),
        "state": (
            mandate.get("UfParlamentar")
            or identification.get("UfParlamentar")
            or ""
        ).upper(),
        "photo_url": force_https(
            identification.get("UrlFotoParlamentar")
        ),
        "profile_url": force_https(
            identification.get("UrlPaginaParlamentar")
        ),
        "email": identification.get(
            "EmailParlamentar",
            "",
        ),
        "gender": basic_data.get("SexoParlamentar", ""),
        "birth_date": basic_data.get("DataNascimento", ""),
        "birthplace": (
            basic_data.get("Naturalidade")
            or basic_data.get("MunicipioNaturalidade")
            or ""
        ),
        "office": identification.get("FormaTratamento", ""),
    }

    cache.set(
        cache_key,
        senator,
        SENATORS_CACHE_TIMEOUT,
    )

    return senator


def get_senator_mandates(senator_id: int) -> list[dict[str, Any]]:
    """Return current and previous mandates with their substitutes."""

    cache_key = f"senator_{senator_id}_mandates"
    cached_mandates = cache.get(cache_key)

    if cached_mandates is not None:
        return cached_mandates

    try:
        response = requests.get(
            f"{SENATE_API_URL}/senador/{senator_id}/mandatos",
            headers=REQUEST_HEADERS,
            timeout=(3.05, 20),
        )
        response.raise_for_status()
        payload = response.json()

    except (requests.RequestException, ValueError) as error:
        raise SenateAPIError(
            "Senator mandate data is temporarily unavailable."
        ) from error

    mandates = parse_senator_mandates(payload)
    cache.set(cache_key, mandates, SENATORS_CACHE_TIMEOUT)

    return mandates


def get_senator_committees(senator_id: int) -> list[dict[str, Any]]:
    """Return current and previous committee memberships."""

    cache_key = f"senator_{senator_id}_committees"
    cached_committees = cache.get(cache_key)

    if cached_committees is not None:
        return cached_committees

    try:
        response = requests.get(
            f"{SENATE_API_URL}/senador/{senator_id}/comissoes",
            headers=REQUEST_HEADERS,
            timeout=(3.05, 20),
        )
        response.raise_for_status()
        payload = response.json()

    except (requests.RequestException, ValueError) as error:
        raise SenateAPIError(
            "Senator committee data is temporarily unavailable."
        ) from error

    committees = parse_senator_committees(payload)
    cache.set(cache_key, committees, SENATORS_CACHE_TIMEOUT)

    return committees


def get_senator_authorships(senator_id: int) -> list[dict[str, Any]]:
    """Return matters authored or coauthored by a senator."""

    cache_key = f"senator_{senator_id}_authorships"
    cached_authorships = cache.get(cache_key)

    if cached_authorships is not None:
        return cached_authorships

    try:
        response = requests.get(
            f"{SENATE_API_URL}/senador/{senator_id}/autorias",
            headers=REQUEST_HEADERS,
            timeout=(3.05, 30),
        )
        response.raise_for_status()
        payload = response.json()

    except (requests.RequestException, ValueError) as error:
        raise SenateAPIError(
            "Senator proposition data is temporarily unavailable."
        ) from error

    authorships = parse_senator_authorships(payload)
    cache.set(cache_key, authorships, SENATORS_CACHE_TIMEOUT)

    return authorships


def get_senator_votes(senator_id: int) -> list[dict[str, Any]]:
    """Return nominal voting records published for a senator."""

    cache_key = f"senator_{senator_id}_votes"
    cached_votes = cache.get(cache_key)

    if cached_votes is not None:
        return cached_votes

    try:
        response = requests.get(
            f"{SENATE_API_URL}/senador/{senator_id}/votacoes",
            headers=REQUEST_HEADERS,
            timeout=(3.05, 30),
        )
        response.raise_for_status()
        payload = response.json()

    except (requests.RequestException, ValueError) as error:
        raise SenateAPIError(
            "Senator voting data is temporarily unavailable."
        ) from error

    votes = parse_senator_votes(payload)
    cache.set(cache_key, votes, SENATORS_CACHE_TIMEOUT)

    return votes
