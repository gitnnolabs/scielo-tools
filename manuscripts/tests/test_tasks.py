from unittest.mock import MagicMock

import pytest

from manuscripts.tasks import process_input


@pytest.mark.django_db
def test_process_input_task_delegates_to_processing(processing, monkeypatch):
    delegate = MagicMock()
    monkeypatch.setattr("manuscripts.tasks.processing.process_input", delegate)

    process_input.run(processing.pk, start_action="xml_validation")

    delegate.assert_called_once_with(process_input, processing.pk, "xml_validation")
