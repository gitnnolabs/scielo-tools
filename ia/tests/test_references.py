from ia.references import mark_reference, mark_references


class ServiceStub:
    def __init__(self, *_args, **_kwargs):
        pass

    def run(self, _reference_text):
        return {
            "choices": [
                {"message": {"content": '{"reftype":"journal"}'}},
            ]
        }


class ServiceFailureStub:
    def __init__(self, *_args, **_kwargs):
        pass

    def run(self, _reference_text):
        raise ValueError("boom")


def test_mark_reference_returns_choices(monkeypatch):
    monkeypatch.setattr("ia.references.LLMService", ServiceStub)

    result = list(mark_reference("A reference"))

    assert result == ['{"reftype":"journal"}']


def test_mark_reference_returns_error_message_on_unexpected_exception(monkeypatch):
    monkeypatch.setattr("ia.references.LLMService", ServiceFailureStub)

    result = list(mark_reference("A reference"))

    assert len(result) == 1
    assert result[0].startswith("An unexpected error occurred: ")


def test_mark_references_processes_non_empty_lines(monkeypatch):
    monkeypatch.setattr("ia.references.LLMService", ServiceStub)

    result = list(mark_references("Ref A\n\nRef B"))

    assert len(result) == 2
    assert result[0]["references"] == "Ref A"
    assert result[1]["references"] == "Ref B"
    assert result[0]["choices"] == ['{"reftype":"journal"}']
