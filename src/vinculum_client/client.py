from __future__ import annotations

import math
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import httpx

_QUERY_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,63}")
_BEARER_TOKEN = re.compile(r"[!-~]{1,512}")


@dataclass(frozen=True)
class QueryResult:
    """Rows and metadata from a successful Vinculum query."""

    rows: list[dict[str, Any]]
    row_count: int
    truncated: bool


class VinculumError(RuntimeError):
    """An API, HTTP, transport, or response-format failure."""

    def __init__(self, message: str, *, code: str, status_code: int | None = None):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class VinculumClient:
    """Run authenticated queries through Vinculum's v1 API.

    Pass the deployment URL, including any reverse proxy prefix, as ``base_url``.
    """

    def __init__(
        self, base_url: str, token: str | None = None, *, timeout: float = 30
    ) -> None:
        url = httpx.URL(base_url)
        if (
            url.scheme not in {"http", "https"}
            or not url.host
            or url.userinfo
            or "?" in base_url
            or "#" in base_url
        ):
            raise ValueError(
                "base_url must be an HTTP or HTTPS URL without credentials, a query, or a fragment."
            )
        if token is None:
            token = os.environ.get("VINCULUM_TOKEN")
        if not isinstance(token, str) or not _BEARER_TOKEN.fullmatch(token):
            raise ValueError("Pass a bearer token or set VINCULUM_TOKEN.")
        if not math.isfinite(timeout) or timeout <= 0 or isinstance(timeout, bool):
            raise ValueError("timeout must be a positive number of seconds.")

        self._http = httpx.Client(
            base_url=url,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=timeout,
            follow_redirects=False,
        )

    def query(self, name: str, params: Mapping[str, Any] | None = None) -> QueryResult:
        """POST named JSON parameters to a configured query and return its result."""
        if not isinstance(name, str) or not _QUERY_NAME.fullmatch(name):
            raise ValueError("name must be a configured query name.")
        if params is not None and (
            not isinstance(params, Mapping) or any(not isinstance(key, str) for key in params)
        ):
            raise TypeError("params must be a mapping with string keys.")

        body = {} if params is None else dict(params)
        try:
            response = self._http.post(f"v1/queries/{name}", json=body)
        except httpx.RequestError as exc:
            message = str(exc) or "The request to Vinculum failed."
            raise VinculumError(message, code="transport_error") from exc

        try:
            payload = response.json()
        except ValueError:
            payload = None
        if not response.is_success:
            self._raise_http_error(response.status_code, payload)

        if isinstance(payload, dict):
            rows = payload.get("rows")
            count = payload.get("row_count")
            truncated = payload.get("truncated")
            if (
                isinstance(rows, list)
                and all(isinstance(row, dict) for row in rows)
                and type(count) is int
                and count == len(rows)
                and type(truncated) is bool
            ):
                return QueryResult(rows, count, truncated)
        raise VinculumError(
            "The response did not contain a Vinculum result.",
            code="protocol_error",
            status_code=response.status_code,
        )

    @staticmethod
    def _raise_http_error(status_code: int, payload: Any) -> None:
        detail = payload.get("error") if isinstance(payload, dict) else None
        if isinstance(detail, dict):
            code = detail.get("code")
            message = detail.get("message")
            if isinstance(code, str) and code and isinstance(message, str) and message:
                raise VinculumError(message, code=code, status_code=status_code)

        message = f"Vinculum returned HTTP {status_code}."
        if isinstance(payload, dict) and isinstance(payload.get("detail"), str):
            message += f" {payload['detail']}"
        raise VinculumError(message, code="http_error", status_code=status_code)

    def close(self) -> None:
        """Close the underlying HTTP session."""
        self._http.close()

    def __enter__(self) -> VinculumClient:
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
