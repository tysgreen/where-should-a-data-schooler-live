"""Shared helpers for talking to APIs and saving raw responses.

Every extract script uses these, so retry logic and file handling live in one place.
"""
import gzip
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

sys.path.append(str(Path(__file__).parent.parent))
from config import ROOT, USER_AGENT  # noqa: E402

load_dotenv(ROOT / ".env")  # reads TFL_APP_KEY from a local, git-ignored .env file


def make_session() -> requests.Session:
    """A requests session that automatically retries on rate limits (429) and
    temporary server errors (5xx), waiting longer after each failure (1s, 2s, 4s...)."""
    session = requests.Session()
    retry = Retry(
        total=5,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers["User-Agent"] = USER_AGENT
    return session


def tfl_params(**params) -> dict:
    """Add the TfL API key (if set) to a dict of query parameters."""
    key = os.environ.get("TFL_APP_KEY")
    if key:
        params["app_key"] = key
    return params


def envelope(response_json, **request_info) -> dict:
    """Wrap an API response with what we asked for and when.

    The response itself is kept exactly as received; the extra fields make it
    possible to trace every row in the database back to the request that produced it.
    """
    return {
        "extracted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "request": request_info,
        "response": response_json,
    }


def save_json_gz(data, path: Path) -> None:
    """Save JSON gzipped (API responses compress ~10x). Writes to a temporary file
    first and renames at the end, so a crash never leaves a half-written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        json.dump(data, f)
    tmp.replace(path)


def load_json_gz(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)
