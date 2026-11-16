"""Check: one finding a risk analysis makes, and the details it carries."""

import pytest

from app.model.check import Check


def _check(status="passed", **extra):
    return Check("benchmark", "TOTAL_WEALTH", "Total wealth", "wealth", status, "detail", **extra)


def test_check_group_defaults_to_its_label():
    assert _check().group == "Total wealth"
    assert _check(group="Wealth").group == "Wealth"


def test_check_rejects_an_unknown_status():
    with pytest.raises(ValueError):
        _check(status="broken")


def test_check_status_setter_validates_too():
    check = _check()
    check.status = "explained"
    assert check.status == "explained"
    with pytest.raises(ValueError):
        check.status = "maybe"


def test_check_to_dict_keeps_the_shape_the_report_reads():
    assert _check().to_dict() == {
        "feature": "benchmark", "check": "TOTAL_WEALTH", "label": "Total wealth", "theme": "wealth",
        "status": "passed", "detail": "detail", "explanation": "", "group": "Total wealth"}


def test_check_to_dict_adds_sources_and_supports_only_when_given():
    data = _check(sources=["tax.pdf"], supports=["T2"]).to_dict()
    assert data["sources"] == ["tax.pdf"]
    assert data["supports"] == ["T2"]


def test_check_lists_cannot_be_changed_from_outside():
    check = _check(sources=["tax.pdf"])
    check.sources.append("other.pdf")
    assert check.sources == ["tax.pdf"]


def test_a_check_keeps_the_extra_details_a_feature_attaches():
    row = {"feature": "crime", "check": "TYPOLOGY", "label": "Trade-based laundering", "theme": "pattern",
           "status": "weak", "detail": "1 of 2 signs fired", "explanation": "", "group": "Trade-based laundering",
           "signs": ["counterparty_unnamed"], "match": "partial", "typology_id": "tbml"}
    check = Check.from_dict(row)
    assert check.status == "weak"
    assert check.to_dict() == row


def test_a_check_round_trips_sources_even_when_empty():
    row = {"feature": "documents", "check": "UNDECLARED_INCOME", "label": "Income", "theme": "sources",
           "status": "failed", "detail": "x", "explanation": "", "group": "Income", "sources": [], "supports": ["T2"]}
    assert Check.from_dict(row).to_dict() == row


def test_a_check_reads_back_the_extra_details_a_feature_attached():
    check = _check(status="failed")
    check.set_extra("independent", True)
    check.set_extra("signs", ["counterparty_unnamed"])
    assert check.extra("independent") is True
    assert check.extra("signs") == ["counterparty_unnamed"]
    assert check.extra("match") is None and check.extra("match", "no_match") == "no_match"
    assert list(check.to_dict())[-2:] == ["independent", "signs"]


@pytest.mark.parametrize("name", ["", "status", "label", "sources", "supports", 3])
def test_a_check_will_not_take_a_named_field_as_an_extra_detail(name):
    with pytest.raises(ValueError):
        _check().set_extra(name, "x")
    with pytest.raises(ValueError):
        _check(extra={name: "x"})


def test_a_check_made_with_empty_lists_saves_them_after_its_extra_details():
    check = Check("documents", "GIFT", "Gift", "people", "failed", "x", sources=[], supports=["fraud"],
                  extra={"note": 1})
    assert list(check.to_dict().items())[-3:] == [("supports", ["fraud"]), ("note", 1), ("sources", [])]
    assert "sources" not in _check().to_dict() and "supports" not in _check().to_dict()
