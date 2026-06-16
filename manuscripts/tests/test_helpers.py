from types import SimpleNamespace

from manuscripts.utils.helpers import _block, _raw_reference, to_dict_list


def test_block_returns_paragraph_structure():
    assert _block("<p>", "Hello") == {
        "type": "paragraph",
        "value": {"label": "<p>", "paragraph": "Hello"},
    }


def test_block_accepts_custom_block_type():
    assert _block("<sec>", "Section", block_type="paragraph_with_language") == {
        "type": "paragraph_with_language",
        "value": {"label": "<sec>", "paragraph": "Section"},
    }


def test_raw_reference_builds_ref_paragraph():
    assert _raw_reference(3, "Citation text.") == {
        "type": "ref_paragraph",
        "value": {
            "label": "<p>",
            "refid": "B3",
            "paragraph": "Citation text.",
            "authors": [],
        },
    }


def test_to_dict_list_returns_empty_for_falsy_values():
    assert to_dict_list(None) == []
    assert to_dict_list([]) == []


def test_to_dict_list_returns_plain_list_unchanged():
    data = [{"type": "paragraph", "value": {"label": "<p>", "paragraph": "x"}}]
    assert to_dict_list(data) is data


def test_to_dict_list_uses_stream_block_get_prep_value():
    class FakeStreamValue:
        stream_block = SimpleNamespace(
            get_prep_value=lambda stream: [{"type": "paragraph", "value": {"prepared": True}}]
        )

    assert to_dict_list(FakeStreamValue()) == [{"type": "paragraph", "value": {"prepared": True}}]
