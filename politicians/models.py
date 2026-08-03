from decimal import Decimal

from django.db import models


class Voting(models.Model):
    """A voting session published by the Chamber of Deputies."""

    external_id = models.CharField(
        max_length=100,
        primary_key=True,
    )

    voting_date = models.DateField(
        null=True,
        blank=True,
        db_index=True,
    )

    description = models.TextField(
        blank=True,
    )

    result = models.TextField(
        blank=True,
    )

    approved = models.BooleanField(
        null=True,
        blank=True,
    )

    organization_id = models.IntegerField(
        null=True,
        blank=True,
    )

    organization_name = models.CharField(
        max_length=255,
        blank=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-voting_date", "-external_id"]

    def __str__(self):
        return f"{self.external_id} - {self.voting_date}"


class DeputyVote(models.Model):
    """A vote registered by a deputy in a voting session."""

    voting = models.ForeignKey(
        Voting,
        on_delete=models.CASCADE,
        related_name="deputy_votes",
    )

    deputy_id = models.PositiveBigIntegerField(
        db_index=True,
    )

    deputy_name = models.CharField(
        max_length=255,
        blank=True,
    )

    party = models.CharField(
        max_length=30,
        blank=True,
    )

    state = models.CharField(
        max_length=2,
        blank=True,
    )

    vote = models.CharField(
        max_length=50,
    )

    vote_registered_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = [
            "-voting__voting_date",
            "-vote_registered_at",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=["voting", "deputy_id"],
                name="unique_deputy_vote_per_voting",
            )
        ]

    def __str__(self):
        return (
            f"{self.deputy_name or self.deputy_id}: "
            f"{self.vote}"
        )


class Municipality(models.Model):
    """An official São Paulo municipality published by IBGE."""

    ibge_code = models.PositiveIntegerField(primary_key=True)
    name = models.CharField(max_length=150, db_index=True)
    slug = models.SlugField(max_length=180, unique=True)
    state = models.CharField(max_length=2, default="SP")
    immediate_region = models.CharField(max_length=150, blank=True)
    intermediate_region = models.CharField(max_length=150, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "municipalities"

    def __str__(self):
        return f"{self.name} ({self.state})"

    @property
    def mayor(self):
        return next(
            (
                officeholder
                for officeholder in self.officeholders.all()
                if officeholder.role
                == MunicipalOfficeholder.Role.MAYOR
            ),
            None,
        )

    @property
    def vice_mayor(self):
        return next(
            (
                officeholder
                for officeholder in self.officeholders.all()
                if officeholder.role
                == MunicipalOfficeholder.Role.VICE_MAYOR
            ),
            None,
        )


class MunicipalOfficeholder(models.Model):
    """A mayor or vice-mayor elected in data published by the TSE."""

    class Role(models.TextChoices):
        MAYOR = "MAYOR", "Mayor"
        VICE_MAYOR = "VICE_MAYOR", "Vice-mayor"

    municipality = models.ForeignKey(
        Municipality,
        on_delete=models.CASCADE,
        related_name="officeholders",
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    tse_candidate_id = models.PositiveBigIntegerField(db_index=True)
    tse_municipality_code = models.CharField(max_length=10)
    name = models.CharField(max_length=255)
    ballot_name = models.CharField(max_length=255, blank=True)
    social_name = models.CharField(max_length=255, blank=True)
    party = models.CharField(max_length=30, blank=True)
    party_name = models.CharField(max_length=150, blank=True)
    coalition_name = models.CharField(max_length=255, blank=True)
    coalition_composition = models.TextField(blank=True)
    birth_date = models.DateField(null=True, blank=True)
    birth_state = models.CharField(max_length=2, blank=True)
    gender = models.CharField(max_length=40, blank=True)
    education = models.CharField(max_length=100, blank=True)
    marital_status = models.CharField(max_length=60, blank=True)
    race = models.CharField(max_length=40, blank=True)
    occupation = models.CharField(max_length=150, blank=True)
    election_date = models.DateField()
    election_type = models.CharField(max_length=100)
    election_round = models.PositiveSmallIntegerField(default=1)
    electoral_status = models.CharField(max_length=60)
    source_url = models.URLField(max_length=500)
    declared_assets_total = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    declared_assets_count = models.PositiveIntegerField(default=0)
    asset_categories = models.JSONField(default=list, blank=True)
    campaign_revenue_total = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    campaign_revenue_count = models.PositiveIntegerField(default=0)
    revenue_categories = models.JSONField(default=list, blank=True)
    campaign_expense_total = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    campaign_expense_count = models.PositiveIntegerField(default=0)
    expense_categories = models.JSONField(default=list, blank=True)
    finance_data_imported_at = models.DateTimeField(null=True, blank=True)
    imported_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["role", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["municipality", "role"],
                name="unique_municipal_officeholder_role",
            )
        ]

    def __str__(self):
        return (
            f"{self.get_role_display()} of "
            f"{self.municipality.name}: {self.name}"
        )

    @staticmethod
    def _format_brl(value):
        formatted = f"{value:,.2f}"
        formatted = formatted.replace(",", "_").replace(".", ",")
        return "R$ " + formatted.replace("_", ".")

    @property
    def formatted_declared_assets_total(self):
        return self._format_brl(self.declared_assets_total)

    @property
    def formatted_campaign_revenue_total(self):
        return self._format_brl(self.campaign_revenue_total)

    @property
    def formatted_campaign_expense_total(self):
        return self._format_brl(self.campaign_expense_total)


class Candidate(models.Model):
    """A candidacy published in the official TSE open dataset."""

    tse_candidate_id = models.PositiveBigIntegerField(primary_key=True)
    municipality = models.ForeignKey(
        Municipality,
        on_delete=models.SET_NULL,
        related_name="candidates",
        null=True,
        blank=True,
    )
    tse_municipality_code = models.CharField(max_length=10, db_index=True)
    election_year = models.PositiveSmallIntegerField(db_index=True)
    election_date = models.DateField(db_index=True)
    election_type = models.CharField(max_length=100)
    election_description = models.CharField(max_length=180)
    election_scope = models.CharField(max_length=40, blank=True, db_index=True)
    election_round = models.PositiveSmallIntegerField(default=1)
    office = models.CharField(max_length=80, db_index=True)
    candidate_number = models.PositiveIntegerField()
    name = models.CharField(max_length=255)
    ballot_name = models.CharField(max_length=255, db_index=True)
    social_name = models.CharField(max_length=255, blank=True)
    party = models.CharField(max_length=30, db_index=True)
    party_name = models.CharField(max_length=150, blank=True)
    federation_name = models.CharField(max_length=255, blank=True)
    federation_composition = models.TextField(blank=True)
    coalition_name = models.CharField(max_length=255, blank=True)
    coalition_composition = models.TextField(blank=True)
    birth_date = models.DateField(null=True, blank=True)
    birth_state = models.CharField(max_length=2, blank=True)
    gender = models.CharField(max_length=40, blank=True)
    education = models.CharField(max_length=100, blank=True)
    marital_status = models.CharField(max_length=60, blank=True)
    race = models.CharField(max_length=40, blank=True)
    occupation = models.CharField(max_length=150, blank=True)
    candidacy_status = models.CharField(max_length=80, db_index=True)
    result_status = models.CharField(max_length=80, blank=True, db_index=True)
    declared_assets_total = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    declared_assets_count = models.PositiveIntegerField(default=0)
    asset_categories = models.JSONField(default=list, blank=True)
    assets_imported_at = models.DateTimeField(null=True, blank=True)
    campaign_revenue_total = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    campaign_revenue_count = models.PositiveIntegerField(default=0)
    revenue_categories = models.JSONField(default=list, blank=True)
    revenue_imported_at = models.DateTimeField(null=True, blank=True)
    campaign_expense_total = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    campaign_expense_count = models.PositiveIntegerField(default=0)
    expense_categories = models.JSONField(default=list, blank=True)
    expenses_imported_at = models.DateTimeField(null=True, blank=True)
    has_government_proposal = models.BooleanField(default=False)
    proposal_checked_at = models.DateTimeField(null=True, blank=True)
    source_url = models.URLField(max_length=500)
    imported_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-election_date", "office", "ballot_name"]

    def __str__(self):
        return (
            f"{self.ballot_name} ({self.party}) - "
            f"{self.office}/{self.election_year}"
        )

    @property
    def formatted_declared_assets_total(self):
        return MunicipalOfficeholder._format_brl(
            self.declared_assets_total
        )

    @property
    def formatted_campaign_revenue_total(self):
        return MunicipalOfficeholder._format_brl(
            self.campaign_revenue_total
        )

    @property
    def formatted_campaign_expense_total(self):
        return MunicipalOfficeholder._format_brl(
            self.campaign_expense_total
        )
