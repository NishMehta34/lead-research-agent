import pytest

from app.llm import chat_json, parse_json


def test_parse_json_handles_fences_and_extra_text():
    assert parse_json('Sure!\n```json\n{"a": 1}\n```') == {"a": 1}


def test_parse_json_raises_when_no_object():
    with pytest.raises(ValueError):
        parse_json("no json here")


def test_chat_json_retries_once_on_bad_reply():
    replies = iter(["not json", '{"ok": true}'])

    class Flaky:
        calls = 0

        def chat(self, system, user):
            Flaky.calls += 1
            return next(replies)

    assert chat_json(Flaky(), "sys", "user") == {"ok": True}
    assert Flaky.calls == 2
