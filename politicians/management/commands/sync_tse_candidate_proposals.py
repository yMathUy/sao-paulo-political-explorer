from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from politicians.models import Candidate
from politicians.services.tse_proposals import (
    TSEProposalError,
    get_proposal_candidate_ids,
)


class Command(BaseCommand):
    help = "Check government proposals published for São Paulo candidates."

    def add_arguments(self, parser):
        parser.add_argument("--year", type=int, help="Election year to check.")

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
            proposal_ids = get_proposal_candidate_ids(election_year)
        except TSEProposalError as error:
            raise CommandError(str(error)) from error

        candidates = list(
            Candidate.objects.filter(election_year=election_year)
        )
        checked_at = timezone.now()
        for candidate in candidates:
            candidate.has_government_proposal = (
                candidate.tse_candidate_id in proposal_ids
            )
            candidate.proposal_checked_at = checked_at

        Candidate.objects.bulk_update(
            candidates,
            ["has_government_proposal", "proposal_checked_at"],
            batch_size=500,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"{len(proposal_ids)} proposals found for {election_year}."
            )
        )
