import csv
import io
import zipfile
from collections import defaultdict
from decimal import Decimal, InvalidOperation

import requests


def assets_archive_url(year):
    return (
        "https://cdn.tse.jus.br/estatistica/sead/odsele/"
        f"bem_candidato/bem_candidato_{year}.zip"
    )


TSE_ASSETS_URL = assets_archive_url(2024)
def accounts_archive_url(year):
    return (
        "https://cdn.tse.jus.br/estatistica/sead/odsele/"
        "prestacao_contas/"
        f"prestacao_de_contas_eleitorais_candidatos_{year}.zip"
    )


TSE_ACCOUNTS_URL = accounts_archive_url(2024)
TSE_ACCOUNTS_DATASET_URL = (
    "https://dadosabertos.tse.jus.br/dataset/"
    "prestacao-de-contas-eleitorais-2024"
)


class TSEFinancesError(Exception):
    """Raised when official TSE finance data cannot be loaded."""


class HTTPRangeReader(io.RawIOBase):
    """Seekable HTTP reader that caches small byte ranges of a large ZIP."""

    def __init__(self, url, timeout=90, block_size=8 * 1024 * 1024):
        self.url = url
        self.timeout = timeout
        self.block_size = block_size
        self.session = requests.Session()
        response = self.session.get(
            url,
            headers={
                "Range": "bytes=0-0",
                "Accept-Encoding": "identity",
            },
            timeout=timeout,
        )
        response.raise_for_status()
        content_range = response.headers.get("Content-Range", "")
        if response.status_code != 206 or "/" not in content_range:
            raise TSEFinancesError(
                "The TSE server did not provide the ZIP file size."
            )
        self.size = int(content_range.rsplit("/", 1)[1])
        self.position = 0
        self.cache = response.content
        self.cache_start = 0

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=io.SEEK_SET):
        if whence == io.SEEK_SET:
            position = offset
        elif whence == io.SEEK_CUR:
            position = self.position + offset
        elif whence == io.SEEK_END:
            position = self.size + offset
        else:
            raise ValueError("Unsupported seek mode.")

        self.position = max(0, position)
        return self.position

    def read(self, size=-1):
        if size is None or size < 0:
            size = self.size - self.position
        if size == 0 or self.position >= self.size:
            return b""

        chunks = []
        remaining = min(size, self.size - self.position)

        while remaining:
            cache_end = self.cache_start + len(self.cache)
            if not (
                self.cache_start <= self.position < cache_end
            ):
                self._fetch_range(max(remaining, self.block_size))
                cache_end = self.cache_start + len(self.cache)

            available = min(remaining, cache_end - self.position)
            start = self.position - self.cache_start
            chunks.append(self.cache[start:start + available])
            self.position += available
            remaining -= available

        return b"".join(chunks)

    def _fetch_range(self, size):
        self.cache_start = self.position
        end = min(self.size - 1, self.position + size - 1)
        response = self.session.get(
            self.url,
            headers={
                "Range": f"bytes={self.position}-{end}",
                "Accept-Encoding": "identity",
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        if response.status_code != 206:
            raise TSEFinancesError(
                "The TSE server did not honor selective ZIP reading."
            )
        self.cache = response.content

    def close(self):
        self.session.close()
        super().close()


def parse_decimal(value):
    normalized = (value or "0").strip().replace(".", "")
    normalized = normalized.replace(",", ".")
    try:
        return Decimal(normalized)
    except InvalidOperation:
        return Decimal("0.00")


def format_brl(value):
    formatted = f"{value:,.2f}"
    formatted = formatted.replace(",", "_").replace(".", ",")
    return "R$ " + formatted.replace("_", ".")


def summarize_candidate_rows(
    rows,
    candidate_ids,
    value_field,
    category_field,
):
    summaries = defaultdict(
        lambda: {
            "total": Decimal("0.00"),
            "count": 0,
            "categories": defaultdict(lambda: Decimal("0.00")),
        }
    )

    for row in rows:
        try:
            candidate_id = int(row.get("SQ_CANDIDATO") or 0)
        except ValueError:
            continue
        if candidate_id not in candidate_ids:
            continue

        amount = parse_decimal(row.get(value_field))
        category = row.get(category_field) or "Not specified"
        summary = summaries[candidate_id]
        summary["total"] += amount
        summary["count"] += 1
        summary["categories"][category] += amount

    results = {}
    for candidate_id, summary in summaries.items():
        categories = sorted(
            summary["categories"].items(),
            key=lambda item: item[1],
            reverse=True,
        )[:5]
        results[candidate_id] = {
            "total": summary["total"],
            "count": summary["count"],
            "categories": [
                {
                    "name": name.title(),
                    "amount": str(amount),
                    "formatted_amount": format_brl(amount),
                }
                for name, amount in categories
            ],
        }
    return results


def _read_sp_csv(archive, filename):
    source = archive.open(filename)
    text = io.TextIOWrapper(source, encoding="cp1252", newline="")
    return text, csv.DictReader(text, delimiter=";")


def get_municipal_candidate_finances(candidate_ids):
    candidate_ids = set(candidate_ids)
    try:
        with HTTPRangeReader(TSE_ASSETS_URL) as remote_file:
            with zipfile.ZipFile(remote_file) as archive:
                text, rows = _read_sp_csv(
                    archive,
                    "bem_candidato_2024_SP.csv",
                )
                with text:
                    assets = summarize_candidate_rows(
                        rows,
                        candidate_ids,
                        "VR_BEM_CANDIDATO",
                        "DS_TIPO_BEM_CANDIDATO",
                    )

        with HTTPRangeReader(TSE_ACCOUNTS_URL) as remote_file:
            with zipfile.ZipFile(remote_file) as archive:
                text, rows = _read_sp_csv(
                    archive,
                    "receitas_candidatos_2024_SP.csv",
                )
                with text:
                    revenues = summarize_candidate_rows(
                        rows,
                        candidate_ids,
                        "VR_RECEITA",
                        "DS_ORIGEM_RECEITA",
                    )

                text, rows = _read_sp_csv(
                    archive,
                    "despesas_contratadas_candidatos_2024_SP.csv",
                )
                with text:
                    expenses = summarize_candidate_rows(
                        rows,
                        candidate_ids,
                        "VR_DESPESA_CONTRATADA",
                        "DS_ORIGEM_DESPESA",
                    )
    except (
        requests.RequestException,
        zipfile.BadZipFile,
        KeyError,
        OSError,
        ValueError,
    ) as error:
        raise TSEFinancesError(
            "Could not load official TSE finance data."
        ) from error

    return {
        "assets": assets,
        "revenues": revenues,
        "expenses": expenses,
    }


def get_candidate_assets(candidate_ids, year=2024):
    try:
        with HTTPRangeReader(assets_archive_url(year)) as remote_file:
            with zipfile.ZipFile(remote_file) as archive:
                text, rows = _read_sp_csv(
                    archive,
                    f"bem_candidato_{year}_SP.csv",
                )
                with text:
                    return summarize_candidate_rows(
                        rows,
                        set(candidate_ids),
                        "VR_BEM_CANDIDATO",
                        "DS_TIPO_BEM_CANDIDATO",
                    )
    except (
        requests.RequestException,
        zipfile.BadZipFile,
        KeyError,
        OSError,
        ValueError,
    ) as error:
        raise TSEFinancesError(
            "Could not load official TSE asset data."
        ) from error


def get_candidate_revenues(candidate_ids, year=2024):
    try:
        with HTTPRangeReader(accounts_archive_url(year)) as remote_file:
            with zipfile.ZipFile(remote_file) as archive:
                text, rows = _read_sp_csv(
                    archive,
                    f"receitas_candidatos_{year}_SP.csv",
                )
                with text:
                    return summarize_candidate_rows(
                        rows,
                        set(candidate_ids),
                        "VR_RECEITA",
                        "DS_ORIGEM_RECEITA",
                    )
    except (
        requests.RequestException,
        zipfile.BadZipFile,
        KeyError,
        OSError,
        ValueError,
    ) as error:
        raise TSEFinancesError(
            "Could not load official TSE campaign revenue data."
        ) from error


def get_candidate_expenses(candidate_ids, year):
    try:
        with HTTPRangeReader(accounts_archive_url(year)) as remote_file:
            with zipfile.ZipFile(remote_file) as archive:
                text, rows = _read_sp_csv(
                    archive,
                    f"despesas_contratadas_candidatos_{year}_SP.csv",
                )
                with text:
                    return summarize_candidate_rows(
                        rows,
                        set(candidate_ids),
                        "VR_DESPESA_CONTRATADA",
                        "DS_ORIGEM_DESPESA",
                    )
    except (
        requests.RequestException,
        zipfile.BadZipFile,
        KeyError,
        OSError,
        ValueError,
    ) as error:
        raise TSEFinancesError(
            "Could not load official TSE campaign expense data."
        ) from error
