from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from politicians.models import Candidate, Municipality
from politicians.services.tse_candidates import (
    TSECandidatesError,
    get_sao_paulo_candidates,
    normalize_place_name,
)


class Command(BaseCommand):
    help = "Synchronize São Paulo candidacies from the TSE open dataset."

    def add_arguments(self, parser):
        parser.add_argument(
            "--year",
            type=int,
            help=(
                "Election year to synchronize. Defaults to the current "
                "year, or the latest previous even year."
            ),
        )

    @transaction.atomic
    def handle(self, *args, **options):
        current_year = date.today().year
        default_year = (
            current_year
            if current_year % 2 == 0
            else current_year - 1
        )
        election_year = options["year"] or default_year

        try:
            records = get_sao_paulo_candidates(election_year)
        except TSECandidatesError as error:
            raise CommandError(str(error)) from error

        municipalities = {
            normalize_place_name(municipality.name): municipality
            for municipality in Municipality.objects.all()
        }
        aliases = {
            "sao luis do paraitinga": "sao luiz do paraitinga",
        }
        candidates = []

        for record in records:
            municipality_key = record.pop("municipality_key")
            municipality_key = aliases.get(
                municipality_key,
                municipality_key,
            )
            candidates.append(
                Candidate(
                    municipality=(
                        municipalities.get(municipality_key)
                        if record["election_scope"].casefold()
                        == "municipal"
                        else None
                    ),
                    **record,
                )
            )

        source_fields = set(records[0]) if records else set()
        update_fields = sorted(
            source_fields - {"tse_candidate_id", "municipality_key"}
        )
        update_fields.append("municipality")
        Candidate.objects.bulk_create(
            candidates,
            batch_size=500,
            update_conflicts=True,
            update_fields=update_fields,
            unique_fields=["tse_candidate_id"],
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"{len(candidates)} candidacies synchronized."
                f" Election year: {election_year}."
            )
        )
