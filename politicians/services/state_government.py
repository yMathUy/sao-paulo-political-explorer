from typing import Any


ELECTION_SOURCE = (
    "https://www.tse.jus.br/comunicacao/noticias/2022/Outubro/"
    "tarcisio-de-freitas-republicanos-vence-disputa-pelo-"
    "governo-de-sao-paulo"
)

STATE_EXECUTIVE = [
    {
        "slug": "tarcisio-de-freitas",
        "name": "Tarcísio de Freitas",
        "civil_name": "Tarcísio Gomes de Freitas",
        "role": "Governor",
        "photo_url": (
            "https://www.sp.gov.br/wcm/connect/"
            "d236cba9-4c75-4a13-bf55-e23d5b44339f/1/"
            "52607280481_5cb23ee050_c.jpg?MOD=AJPERES"
        ),
        "party_at_election": "Republicanos",
        "mandate_start": "2023-01-01",
        "mandate_end": "2026-12-31",
        "election_year": 2022,
        "election_round": "Second round",
        "election_votes": 12_576_778,
        "election_vote_share": "55.34%",
        "running_mate": "Felicio Ramuth",
        "biography": (
            "Engineer and federal public servant. Before the 2022 "
            "election, he served as Brazil's Minister of Infrastructure."
        ),
        "office_address": (
            "Palácio dos Bandeirantes, Avenida Morumbi, 4500, "
            "São Paulo, SP"
        ),
        "office_source": (
            "https://www.sp.gov.br/sp/institucional/estrutura/governador"
        ),
        "election_source": ELECTION_SOURCE,
        "last_verified": "2026-07-29",
    },
    {
        "slug": "felicio-ramuth",
        "name": "Felicio Ramuth",
        "civil_name": "Felicio Ramuth",
        "role": "Vice Governor",
        "photo_url": (
            "https://www.sp.gov.br/dx/api/dam/v1/collections/"
            "9d6bf3f2-2752-40f8-9b8e-63b6af756813/items/"
            "22ae2bbe-2fde-4264-bb5a-ec9f805ec87a/renditions/"
            "5e0c9009-5aff-4b0e-a24a-3c01b2cb2d4a?binary=true"
        ),
        "party_at_election": "PSD",
        "mandate_start": "2023-01-01",
        "mandate_end": "2026-12-31",
        "election_year": 2022,
        "election_round": "Second round",
        "election_votes": 12_576_778,
        "election_vote_share": "55.34%",
        "running_mate": "Tarcísio de Freitas",
        "biography": (
            "Elected vice governor of São Paulo on the winning ticket "
            "in the second round of the 2022 state election."
        ),
        "office_address": (
            "Palácio dos Bandeirantes, Avenida Morumbi, 4500, "
            "São Paulo, SP"
        ),
        "office_source": (
            "https://www.sp.gov.br/sp/institucional/estrutura/"
            "vice-governador"
        ),
        "election_source": ELECTION_SOURCE,
        "last_verified": "2026-07-29",
    },
]


def get_current_state_executive() -> list[dict[str, Any]]:
    """Return the currently verified São Paulo executive officeholders."""

    return [officeholder.copy() for officeholder in STATE_EXECUTIVE]


def get_state_officeholder(slug: str) -> dict[str, Any] | None:
    """Return a state executive officeholder by stable slug."""

    for officeholder in STATE_EXECUTIVE:
        if officeholder["slug"] == slug:
            return officeholder.copy()

    return None
