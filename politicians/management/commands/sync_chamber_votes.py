from datetime import date
from typing import Any

import requests
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.dateparse import parse_date, parse_datetime
from django.utils import timezone

from politicians.models import DeputyVote, Voting


FILES_BASE_URL = "https://dadosabertos.camara.leg.br/arquivos"

REQUEST_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "SaoPauloPoliticalExplorer/1.0",
}


def extract_records(payload: Any) -> list[dict[str, Any]]:
    """Extract records from different official JSON structures."""

    if isinstance(payload, list):
        return [
            record
            for record in payload
            if isinstance(record, dict)
        ]

    if isinstance(payload, dict):
        preferred_keys = (
            "dados",
            "votacoesVotos",
            "votos",
            "votacoes",
        )

        for key in preferred_keys:
            if key not in payload:
                continue

            records = extract_records(payload[key])

            if records:
                return records

        for value in payload.values():
            records = extract_records(value)

            if records:
                return records

    return []


def get_first_value(
    record: dict[str, Any],
    *field_names: str,
    default: Any = None,
) -> Any:
    """Return the first existing non-empty value among possible field names."""

    for field_name in field_names:
        value = record.get(field_name)

        if value not in (None, ""):
            return value

    return default


def parse_integer(value: Any) -> int | None:
    """Convert an API value to an integer when possible."""

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_boolean(value: Any) -> bool | None:
    """Convert common API boolean representations."""

    if isinstance(value, bool):
        return value

    normalized_value = str(value).strip().lower()

    if normalized_value in {"1", "true", "yes", "sim", "s"}:
        return True

    if normalized_value in {"0", "false", "no", "não", "nao", "n"}:
        return False

    return None

def parse_vote_datetime(value: Any):
    """Parse a vote timestamp and attach the configured timezone."""

    if not value:
        return None

    parsed_value = parse_datetime(str(value))

    if parsed_value is None:
        return None

    if timezone.is_naive(parsed_value):
        parsed_value = timezone.make_aware(
            parsed_value,
            timezone.get_current_timezone(),
        )

    return parsed_value

def get_deputy_data(record: dict[str, Any]) -> dict[str, Any]:
    """Return the nested deputy information from a vote record."""

    deputy_data = record.get("deputado_", {})

    if isinstance(deputy_data, dict):
        return deputy_data

    return {}

def download_json(url: str) -> list[dict[str, Any]]:
    """Download and return records from an official Chamber JSON file."""

    try:
        response = requests.get(
            url,
            headers=REQUEST_HEADERS,
            timeout=(5, 120),
        )

        response.raise_for_status()

        return extract_records(response.json())

    except requests.RequestException as error:
        raise CommandError(
            f"Could not download Chamber data from {url}."
        ) from error

    except ValueError as error:
        raise CommandError(
            f"The downloaded file is not valid JSON: {url}."
        ) from error


class Command(BaseCommand):
    help = "Synchronize Chamber voting records for São Paulo deputies."

    def add_arguments(self, parser):
        parser.add_argument(
            "--year",
            type=int,
            default=date.today().year,
            help="Voting year to synchronize.",
        )

        parser.add_argument(
            "--state",
            type=str,
            default="SP",
            help="State abbreviation used to filter deputy votes.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        year = options["year"]
        state = options["state"].strip().upper()

        votings_url = (
            f"{FILES_BASE_URL}/votacoes/json/"
            f"votacoes-{year}.json"
        )

        votes_url = (
            f"{FILES_BASE_URL}/votacoesVotos/json/"
            f"votacoesVotos-{year}.json"
        )

        self.stdout.write(
            self.style.NOTICE(
                f"Downloading voting records for {year}..."
            )
        )

        voting_records = download_json(votings_url)

        voting_objects = []

        for record in voting_records:
            external_id = str(
                get_first_value(record, "id", "idVotacao", default="")
            ).strip()

            if not external_id:
                continue

            voting_date_value = get_first_value(record, "data")

            voting_objects.append(
                Voting(
                    external_id=external_id,
                    voting_date=(
                        parse_date(str(voting_date_value))
                        if voting_date_value
                        else None
                    ),
                    description=str(
                        get_first_value(
                            record,
                            "descricao",
                            default="",
                        )
                    ),
                    result=str(
                        get_first_value(
                            record,
                            "descricaoResultado",
                            "placar",
                            default="",
                        )
                    ),
                    approved=parse_boolean(
                        get_first_value(
                            record,
                            "aprovacao",
                        )
                    ),
                    organization_id=parse_integer(
                        get_first_value(
                            record,
                            "idOrgao",
                        )
                    ),
                    organization_name=str(
                        get_first_value(
                            record,
                            "siglaOrgao",
                            "nomeOrgao",
                            default="",
                        )
                    ),
                )
            )

        Voting.objects.bulk_create(
            voting_objects,
            update_conflicts=True,
            update_fields=[
                "voting_date",
                "description",
                "result",
                "approved",
                "organization_id",
                "organization_name",
            ],
            unique_fields=["external_id"],
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"{len(voting_objects)} voting records synchronized."
            )
        )

        self.stdout.write(
            self.style.NOTICE(
                f"Downloading individual votes for {state}..."
            )
        )

        vote_records = download_json(votes_url)

        state_vote_records = []
            
        for record in vote_records:
            deputy_data = get_deputy_data(record)
            if str(deputy_data.get("siglaUf", "")).upper() == state:
                state_vote_records.append(record)

        voting_ids = {
            str(
                get_first_value(
                    record,
                    "idVotacao",
                    "votacao_id",
                    default="",
                )
            ).strip()
            for record in state_vote_records
        }

        voting_ids.discard("")

        existing_votings = Voting.objects.in_bulk(
            voting_ids,
            field_name="external_id",
        )

        vote_objects = []
        ignored_records = 0

        for record in state_vote_records:
            deputy_data = get_deputy_data(record)
            voting_id = str(
                get_first_value(
                    record,
                    "idVotacao",
                    "votacao_id",
                    default="",
                )
            ).strip()

            deputy_id = parse_integer(deputy_data.get("id"))
        

            voting = existing_votings.get(voting_id)

            if not voting or deputy_id is None:
                ignored_records += 1
                continue

            vote_datetime_value = get_first_value(
                record,
                "dataHoraVoto",
                "dataHoraRegistro",
            )

            vote_objects.append(
                DeputyVote(
                    voting=voting,
                    deputy_id=deputy_id,
                    deputy_name=str(deputy_data.get("nome", "")),
                    party=str(deputy_data.get("siglaPartido", "")),
                    state=str(deputy_data.get("siglaUf", state)).upper(),   
                    vote=str(
                        get_first_value(
                            record,
                            "voto",
                            default="Not informed",
                        )
                    ),
                    vote_registered_at=parse_vote_datetime(
                     vote_datetime_value
                    ),
                )
            )

        DeputyVote.objects.bulk_create(
            vote_objects,
            update_conflicts=True,
            update_fields=[
                "deputy_name",
                "party",
                "state",
                "vote",
                "vote_registered_at",
            ],
            unique_fields=["voting", "deputy_id"],
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"{len(vote_objects)} deputy votes synchronized."
            )
        )

        if ignored_records:
            self.stdout.write(
                self.style.WARNING(
                    f"{ignored_records} incomplete records were ignored."
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Voting synchronization for {year} completed."
            )
        )