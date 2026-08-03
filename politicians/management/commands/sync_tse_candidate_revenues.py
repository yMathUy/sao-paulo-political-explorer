from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from politicians.models import Candidate
from politicians.services.tse_finances import (
    TSEFinancesError,
    get_candidate_revenues,
)


class Command(BaseCommand):
    help = "Synchronize campaign revenue for São Paulo candidates from TSE."

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
            revenues = get_candidate_revenues(
                candidate_ids,
                election_year,
            )
        except TSEFinancesError as error:
            raise CommandError(str(error)) from error

        imported_at = timezone.now()
        for candidate in candidates:
            summary = revenues.get(candidate.tse_candidate_id, {})
            candidate.campaign_revenue_total = summary.get("total", 0)
            candidate.campaign_revenue_count = summary.get("count", 0)
            candidate.revenue_categories = summary.get("categories", [])
            candidate.revenue_imported_at = imported_at

        Candidate.objects.bulk_update(
            candidates,
            [
                "campaign_revenue_total",
                "campaign_revenue_count",
                "revenue_categories",
                "revenue_imported_at",
            ],
            batch_size=500,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Revenue data synchronized for {len(candidates)} "
                f"candidates from {election_year}."
            )
        )
