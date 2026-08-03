import zipfile

import requests
from django.core.cache import cache

from .tse_finances import HTTPRangeReader, TSEFinancesError


def candidate_photos_url(year):
    return (
        "https://cdn.tse.jus.br/estatistica/sead/eleicoes/"
        f"eleicoes{year}/fotos/foto_cand{year}_SP_div.zip"
    )
PHOTO_CACHE_TIMEOUT = 60 * 60 * 24 * 7
PHOTO_FALLBACK_CACHE_TIMEOUT = 60 * 60

PHOTO_PLACEHOLDER_SVG = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 480 360" role="img" aria-label="Photo unavailable">
<rect width="480" height="360" fill="#e8f1f7"/>
<circle cx="240" cy="135" r="62" fill="#9bb6c8"/>
<path d="M118 340c8-83 55-126 122-126s114 43 122 126" fill="#9bb6c8"/>
<circle cx="240" cy="180" r="128" fill="none" stroke="#c7d9e5" stroke-width="3"/>
</svg>"""


class TSEPhotoError(Exception):
    """Raised when an official candidate photo cannot be loaded."""


def get_candidate_photo(candidate_id, year):
    cache_key = f"tse_candidate_photo_{year}_{candidate_id}"
    cached_photo = cache.get(cache_key)
    if cached_photo is not None:
        if cached_photo == b"":
            raise TSEPhotoError(
                "Official candidate photo is unavailable."
            )
        return cached_photo

    filename = f"FSP{candidate_id}_div.jpg"
    try:
        with HTTPRangeReader(candidate_photos_url(year)) as remote_file:
            with zipfile.ZipFile(remote_file) as archive:
                photo = archive.read(filename)
    except (
        TSEFinancesError,
        requests.RequestException,
        zipfile.BadZipFile,
        KeyError,
        OSError,
    ) as error:
        cache.set(
            cache_key,
            b"",
            PHOTO_FALLBACK_CACHE_TIMEOUT,
        )
        raise TSEPhotoError(
            "Official candidate photo is unavailable."
        ) from error

    cache.set(cache_key, photo, PHOTO_CACHE_TIMEOUT)
    return photo
