from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from politicians.models import Municipality
from politicians.services.ibge_api import (
    IBGEAPIError,
    get_sao_paulo_municipalities,
)


class Command(BaseCommand):
    help = "Synchronize São Paulo municipalities from the official IBGE API."

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            records = get_sao_paulo_municipalities()
        except IBGEAPIError as error:
            raise CommandError(str(error)) from error

        municipalities = [
            Municipality(
                ibge_code=record["ibge_code"],
                name=record["name"],
                slug=(
                    f"{slugify(record['name'])}-"
                    f"{record['ibge_code']}"
                ),
                state=record["state"],
                immediate_region=record["immediate_region"],
                intermediate_region=record[
                    "intermediate_region"
                ],
            )
            for record in records
        ]

        Municipality.objects.bulk_create(
            municipalities,
            update_conflicts=True,
            update_fields=[
                "name",
                "slug",
                "state",
                "immediate_region",
                "intermediate_region",
            ],
            unique_fields=["ibge_code"],
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"{len(municipalities)} municipalities synchronized."
            )
        )
