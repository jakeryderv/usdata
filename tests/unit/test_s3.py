from xml.sax.saxutils import escape

import httpx
import pytest

from usdata.protocols.s3 import list_objects


def page(token: str | None, *, truncated: bool = True) -> str:
    continuation = (
        "" if token is None else f"<NextContinuationToken>{escape(token)}</NextContinuationToken>"
    )
    return (
        '<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
        f"<IsTruncated>{str(truncated).lower()}</IsTruncated>{continuation}"
        "<Contents><Key>sample</Key><Size>1</Size></Contents></ListBucketResult>"
    )


@pytest.mark.parametrize("tokens", [[None], [""], [" "], ["a", "a"], ["a", "b", "a"]])
def test_pagination_rejects_missing_or_cycling_tokens(tokens: list[str | None]) -> None:
    requests = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, text=page(tokens[len(requests) - 1]))

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(httpx.RemoteProtocolError, match="continuation token") as error:
            list(list_objects("example", "prefix/", client))
        assert error.value.request is requests[-1]
        assert len(requests) == len(tokens)
        assert not client.is_closed


def test_pagination_preserves_opaque_tokens_and_stops_at_final_page() -> None:
    requests = []
    token = "a+/=& b"

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, text=page(token, truncated=len(requests) == 1))

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        objects = list(list_objects("example", "prefix/", client, page_size=1))
    assert len(objects) == 2
    assert len(requests) == 2
    assert "continuation-token" not in requests[0].url.params
    assert requests[1].url.params["continuation-token"] == token
    assert requests[1].url.params["prefix"] == "prefix/"
    assert requests[1].url.params["max-keys"] == "1"
