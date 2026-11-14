"""Every IO Manager class can be made with its defaults."""

import pytest

from app.interface.case_builder import CaseBuilder
from app.interface.client_form import ClientForm
from app.interface.report_view import ReportView


@pytest.mark.parametrize("io_class", [CaseBuilder, ClientForm, ReportView], ids=lambda cls: cls.__name__)
def test_every_io_class_can_be_made_with_its_defaults(io_class):
    assert isinstance(io_class(), io_class)
