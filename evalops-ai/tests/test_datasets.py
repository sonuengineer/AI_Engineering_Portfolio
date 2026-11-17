import pytest

from app.core.errors import ValidationFailed
from app.services.datasets import content_hash, parse_jsonl


def test_parse_valid_and_defaults():
    rows = parse_jsonl(b'{"input": "q1"}\n\n{"id": "x", "input": "q2", "tags": ["t"]}\n', max_cases=10)
    assert rows[0]["id"] == "case-0001" and rows[1]["tags"] == ["t"] and rows[0]["metadata"] == {}


@pytest.mark.parametrize("content,msg", [
    (b"", "no cases"),
    (b"not json\n", "invalid JSON"),
    (b'[1,2]\n', "JSON object"),
    (b'{"input": ""}\n', "non-empty"),
    (b'{"input": "q", "bogus": 1}\n', "unknown keys"),
    (b'{"input": "q", "tags": "x"}\n', "list of strings"),
    (b'{"id": "a", "input": "q"}\n{"id": "a", "input": "r"}\n', "duplicate"),
    (b"\xff\xfe", "UTF-8"),
])
def test_parse_rejects(content, msg):
    with pytest.raises(ValidationFailed, match=msg):
        parse_jsonl(content, max_cases=10)


def test_max_cases():
    with pytest.raises(ValidationFailed, match="too many"):
        parse_jsonl(b'{"input": "a"}\n{"input": "b"}\n{"input": "c"}\n', max_cases=2)


def test_hash_is_stable_and_content_sensitive():
    a = parse_jsonl(b'{"input": "q", "metadata": {"b": 1, "a": 2}}\n', max_cases=5)
    b = parse_jsonl(b'{"metadata": {"a": 2, "b": 1}, "input": "q"}\n', max_cases=5)
    c = parse_jsonl(b'{"input": "q2"}\n', max_cases=5)
    assert content_hash(a) == content_hash(b) != content_hash(c)
