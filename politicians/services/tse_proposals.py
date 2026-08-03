import re
import zipfile

import requests
from django.core.cache import cache

from .tse_finances import HTTPRangeReader, TSEFinancesError


class TSEProposalError(Exception):
    """Raised when official TSE government proposals cannot be loaded."""


PROPOSAL_CACHE_TIMEOUT = 60 * 60 * 24


def proposal_archive_url(year):
    return (
        "https://cdn.tse.jus.br/estatistica/sead/odsele/"
        "proposta_governo/"
        f"proposta_governo_{year}_SP.zip"
    )


def get_proposal_candidate_ids(year):
    try:
        with HTTPRangeReader(proposal_archive_url(year)) as remote_file:
            with zipfile.ZipFile(remote_file) as archive:
                candidate_ids = set()
                pattern = re.compile(
                    rf"^{year}SP(\d+)_\d+\.pdf$",
                    re.IGNORECASE,
                )
                for filename in archive.namelist():
                    match = pattern.search(filename.rsplit("/", 1)[-1])
                    if match:
                        candidate_ids.add(int(match.group(1)))
                return candidate_ids
    except (
        TSEFinancesError,
        requests.RequestException,
        zipfile.BadZipFile,
        OSError,
        ValueError,
    ) as error:
        raise TSEProposalError(
            "Could not load the official TSE proposal index."
        ) from error


def get_candidate_proposal(candidate_id, year):
    cache_key = f"tse_candidate_proposal_{year}_{candidate_id}"
    cached_proposal = cache.get(cache_key)
    if cached_proposal is not None:
        return cached_proposal

    filename = f"SP/{year}SP{candidate_id}_01.pdf"
    try:
        with HTTPRangeReader(proposal_archive_url(year)) as remote_file:
            with zipfile.ZipFile(remote_file) as archive:
                proposal = archive.read(filename)
    except (
        TSEFinancesError,
        requests.RequestException,
        zipfile.BadZipFile,
        KeyError,
        OSError,
        ValueError,
    ) as error:
        raise TSEProposalError(
            "Official government proposal is unavailable."
        ) from error

    cache.set(cache_key, proposal, PROPOSAL_CACHE_TIMEOUT)
    return proposal
