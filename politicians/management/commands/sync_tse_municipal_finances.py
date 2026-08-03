from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from politicians.models import MunicipalOfficeholder
from politicians.services.tse_finances import (
    TSEFinancesError,
    get_municipal_candidate_finances,
)


class Command(BaseCommand):
    help = (
        "Synchronize assets, campaign revenue and contracted campaign "
        "expenses for elected municipal officeholders from the TSE."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        officeholders = list(MunicipalOfficeholder.objects.all())
        candidate_ids = {
            officeholder.tse_candidate_id
            for officeholder in officeholders
        }

        try:
            finances = get_municipal_candidate_finances(candidate_ids)
        except TSEFinancesError as error:
            raise CommandError(str(error)) from error

        imported_at = timezone.now()
        for officeholder in officeholders:
            candidate_id = officeholder.tse_candidate_id
            assets = finances["assets"].get(candidate_id, {})
            revenues = finances["revenues"].get(candidate_id, {})
            expenses = finances["expenses"].get(candidate_id, {})

            officeholder.declared_assets_total = assets.get("total", 0)
            officeholder.declared_assets_count = assets.get("count", 0)
            officeholder.asset_categories = assets.get("categories", [])
            officeholder.campaign_revenue_total = revenues.get("total", 0)
            officeholder.campaign_revenue_count = revenues.get("count", 0)
            officeholder.revenue_categories = revenues.get("categories", [])
            officeholder.campaign_expense_total = expenses.get("total", 0)
            officeholder.campaign_expense_count = expenses.get("count", 0)
            officeholder.expense_categories = expenses.get("categories", [])
            officeholder.finance_data_imported_at = imported_at

        MunicipalOfficeholder.objects.bulk_update(
            officeholders,
            [
                "declared_assets_total",
                "declared_assets_count",
                "asset_categories",
                "campaign_revenue_total",
                "campaign_revenue_count",
                "revenue_categories",
                "campaign_expense_total",
                "campaign_expense_count",
                "expense_categories",
                "finance_data_imported_at",
            ],
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Finance data synchronized for {len(officeholders)} "
                "municipal officeholders."
            )
        )
