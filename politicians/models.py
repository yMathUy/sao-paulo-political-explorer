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