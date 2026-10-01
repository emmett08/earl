"""Host output cannot expose credentials through application JSON keys."""

import json

import pytest

from mcp.types import AudioContent, EmbeddedResource, ImageContent, ResourceLink, TextContent

from eal.host_redaction import sanitise_response


@pytest.mark.parametrize("token", ["synthetic-bearer-key", 'opaque\\"secret'])
def test_nested_structured_and_encoded_keys_are_redacted_together(token):
    payload = {"nested": [{token: "first", "prefix-" + token + "-suffix": token}]}
    response = {"result": payload, "content": [{"type": "text", "text": json.dumps(payload)}]}
    sanitised = sanitise_response(response, token)
    expected = {"nested": [{"[redacted]": "first", "prefix-[redacted]-suffix": "[redacted]"}]}
    assert sanitised["result"] == expected
    assert json.loads(sanitised["content"][0]["text"]) == expected
    assert sanitised["content"][0]["type"] == "text"
    assert token not in json.dumps(sanitised)
    assert response["result"] == {"nested": [{token: "first", "prefix-" + token + "-suffix": token}]}


def test_unicode_escaped_credentials_in_keys_are_decoded_before_redaction():
    token = "synthetic-secret"
    escaped = "".join(f"\\u{ord(character):04x}" for character in token)
    encoded = '{"' + escaped + '":{"prefix-' + escaped + '":true}}'
    response = {"content": [{"type": "text", "text": encoded}]}
    sanitised = sanitise_response(response, token)
    assert json.loads(sanitised["content"][0]["text"]) == {"[redacted]": {"prefix-[redacted]": True}}


def test_keys_in_repeatedly_encoded_json_strings_are_redacted():
    token = "synthetic-secret"
    response = {"result": {"encoded": json.dumps(json.dumps({token: token}))}}
    sanitised = sanitise_response(response, token)
    assert json.loads(json.loads(sanitised["result"]["encoded"])) == {"[redacted]": "[redacted]"}


@pytest.mark.parametrize("encoded", [False, True])
@pytest.mark.parametrize("reverse", [False, True])
def test_key_collisions_fail_without_silently_overwriting_a_value(encoded, reverse):
    token = "synthetic-secret"
    items = [(token, "first"), ("[redacted]", "second")]
    payload = dict(reversed(items) if reverse else items)
    response = {"result": json.dumps(payload) if encoded else payload}
    with pytest.raises(ValueError, match="merge distinct JSON object keys") as caught:
        sanitise_response(response, token)
    assert token not in str(caught.value)


@pytest.mark.parametrize("token", ["result", "content", "type", "text", "_meta"])
def test_only_fixed_wrapper_fields_are_exempt_from_key_redaction(token):
    response = {
        "operation": "validate", "protocol_version": "2026-07-28", "is_error": False,
        "result": {token: token},
        "content": [{"type": "text", "text": json.dumps({token: token}), "_meta": {token: token}}],
    }
    sanitised = sanitise_response(response, token)
    assert set(sanitised) == set(response)
    assert sanitised["result"] == {"[redacted]": "[redacted]"}
    block = sanitised["content"][0]
    assert set(block) == {"type", "text", "_meta"}
    assert block["type"] == "text"
    assert block["_meta"] == {"[redacted]": "[redacted]"}
    assert json.loads(block["text"]) == {"[redacted]": "[redacted]"}


@pytest.mark.parametrize("by_alias", [False, True])
@pytest.mark.parametrize("token", ["type", "mime_type", "mimeType", "meta", "_meta"])
@pytest.mark.parametrize("block", [
    TextContent(text="value"),
    ImageContent(data="dmFsdWU=", mimeType="image/png"),
    AudioContent(data="dmFsdWU=", mimeType="audio/wav"),
    ResourceLink(name="value", uri="https://example.invalid/resource"),
    EmbeddedResource(resource={"uri": "https://example.invalid/resource", "text": "value"}),
])
def test_sdk_content_wrappers_preserve_python_field_names_and_wire_aliases(block, token, by_alias):
    original = block.model_copy(update={"meta": {token: token}}).model_dump(
        mode="json", exclude_none=True, by_alias=by_alias,
    )
    sanitised = sanitise_response({"content": [original]}, token)["content"][0]
    assert set(sanitised) == set(original)
    assert sanitised["type"] == original["type"]
    assert sanitised["_meta" if by_alias else "meta"] == {"[redacted]": "[redacted]"}


def test_unknown_wrapper_fields_and_content_discriminators_are_sanitised():
    token = "synthetic-secret"
    response = {"is_error": False, token: token,
                "content": [{"type": token, token: token}]}
    assert sanitise_response(response, token) == {
        "is_error": False, "[redacted]": "[redacted]",
        "content": [{"type": "[redacted]", "[redacted]": "[redacted]"}],
    }


@pytest.mark.parametrize("encoded", [
    '{"\\u0073\\u0065\\u0063\\u0072\\u0065\\u0074":true,',
    '{"\\u0073\\u0065\\u0063\\u0072\\u0065\\u0074":true,"other":1,"other":2}',
])
def test_unparseable_json_text_is_replaced_instead_of_preserving_escaped_credentials(encoded):
    response = {"content": [{"type": "text", "text": encoded}]}
    assert sanitise_response(response, "secret")["content"][0]["text"] == "[redacted]"


@pytest.mark.parametrize("token", ["redacted", "[redacted]", "[", "a"])
def test_redaction_marker_cannot_contain_the_configured_token(token):
    sanitised = sanitise_response({"result": {token: token}}, token)
    assert sanitised == {"result": {"": ""}}


@pytest.mark.parametrize(("token", "remote_text"), [("a[redacted]b", "aa[redacted]bb"), ("][", "][[")])
def test_marker_boundaries_cannot_reconstruct_the_credential(token, remote_text):
    sanitised = sanitise_response({"result": {remote_text: remote_text}}, token)
    assert sanitised == {"result": {"": ""}}


def test_responses_without_a_credential_are_unchanged():
    response = {"result": {"key": "value"}, "content": [{"type": "text", "text": "{invalid"}]}
    assert sanitise_response(response, None) == response


def test_credential_free_json_text_retains_its_original_formatting():
    encoded = '{\n  "result": true\n}'
    response = {"content": [{"type": "text", "text": encoded}]}
    assert sanitise_response(response, "synthetic-secret") == response
