import json
from functools import partial

import httpx
import pytest

from vinculum_client import QueryResult, VinculumClient, VinculumError


@pytest.fixture
def make_client(monkeypatch):
    monkeypatch.setenv("VINCULUM_TOKEN", "fixture-token")
    original = httpx.Client

    def make(handler):
        monkeypatch.setattr(httpx, "Client", partial(original, transport=httpx.MockTransport(handler)))
        return VinculumClient("https://proxy.test/vinculum/")

    return make


@pytest.mark.parametrize("ids", [[], [1], [1, 2, 3]])
def test_prefixed_query_preserves_array_shape(make_client, ids):
    def handler(request):
        assert str(request.url) == "https://proxy.test/vinculum/v1/queries/by_ids"
        assert request.method == "POST"
        assert request.headers["Authorization"] == "Bearer fixture-token"
        assert json.loads(request.content) == {"ids": ids}
        return httpx.Response(200, json={"rows": [{"amount": "12.5000"}],
                                         "row_count": 1, "truncated": True})

    with make_client(handler) as client:
        assert client.query("by_ids", {"ids": ids}) == QueryResult(
            [{"amount": "12.5000"}], 1, True
        )


def test_no_parameters_sends_an_object(make_client):
    def handler(request):
        assert json.loads(request.content) == {}
        return httpx.Response(200, json={"rows": [], "row_count": 0, "truncated": False})

    with make_client(handler) as client:
        assert client.query("ping").rows == []


def test_api_error_preserves_diagnostic(make_client):
    def handler(_request):
        return httpx.Response(502, json={"error": {
            "code": "query_failed", "message": "no such table: measurements"
        }})

    with make_client(handler) as client, pytest.raises(VinculumError) as caught:
        client.query("broken")
    assert caught.value.code == "query_failed"
    assert caught.value.status_code == 502
    assert str(caught.value) == "no such table: measurements"


@pytest.mark.parametrize(("status", "code"), [(404, "http_error"), (200, "protocol_error")])
def test_non_api_body_is_classified(make_client, status, code):
    with make_client(lambda _: httpx.Response(status, text="<html></html>")) as client:
        with pytest.raises(VinculumError) as caught:
            client.query("ping")
    assert caught.value.code == code
    assert caught.value.status_code == status
