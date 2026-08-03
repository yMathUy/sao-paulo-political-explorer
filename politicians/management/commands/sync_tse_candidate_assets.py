from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from politicians.models import Candidate
from politicians.services.tse_finances import (
    TSEFinancesError,
    get_candidate_assets,
)


class Command(BaseCommand):
    help = "Synchronize declared assets for São Paulo candidates from TSE."

    def add_arguments(self, parser):
        parser.add_argument(
            "--year",
            type=int,
            help="Election year to synchronize.",
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
        candidates = list(
            Candidate.objects.filter(election_year=election_year)
        )
        candidate_ids = {
            candidate.tse_candidate_id
            for candidate in candidates
        }

        try:
            assets = get_candidate_assets(candidate_ids, election_year)
        except TSEFinancesError as error:
            raise CommandError(str(error)) from error

        imported_at = timezone.now()
        for candidate in candidates:
            summary = assets.get(candidate.tse_candidate_id, {})
            candidate.declared_assets_total = summary.get("total", 0)
            candidate.declared_assets_count = summary.get("count", 0)
            candidate.asset_categories = summary.get("categories", [])
            candidate.assets_imported_at = imported_at

        Candidate.objects.bulk_update(
            candidates,
            [
                "declared_assets_total",
                "declared_assets_count",
                "asset_categories",
                "assets_imported_at",
            ],
            batch_size=500,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Asset data synchronized for {len(candidates)} candidates."
                f" Election year: {election_year}."
            )
        )
