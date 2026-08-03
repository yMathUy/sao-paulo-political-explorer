from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from politicians.models import Municipality, MunicipalOfficeholder
from politicians.services.tse_candidates import (
    TSECandidatesError,
    get_elected_municipal_officeholders,
    normalize_place_name,
)


class Command(BaseCommand):
    help = (
        "Synchronize elected São Paulo mayors and vice-mayors "
        "from the official TSE open dataset."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            records = get_elected_municipal_officeholders()
        except TSECandidatesError as error:
            raise CommandError(str(error)) from error

        municipalities = {
            normalize_place_name(municipality.name): municipality
            for municipality in Municipality.objects.all()
        }
        name_aliases = {
            "sao luis do paraitinga": "sao luiz do paraitinga",
        }
        synchronized = 0
        unmatched = set()

        for record in records:
            municipality_key = record.pop("municipality_key")
            municipality_key = name_aliases.get(
                municipality_key,
                municipality_key,
            )
            municipality = municipalities.get(municipality_key)
            municipality_name = record.pop("municipality_name")

            if not municipality:
                unmatched.add(municipality_name)
                continue

            MunicipalOfficeholder.objects.update_or_create(
                municipality=municipality,
                role=record["role"],
                defaults=record,
            )
            synchronized += 1

        if unmatched:
            self.stderr.write(
                self.style.WARNING(
                    "Municipalities not matched: "
                    + ", ".join(sorted(unmatched))
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"{synchronized} municipal officeholders synchronized."
            )
        )
