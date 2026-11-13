"""ClientProfile and ReviewStatus: the two parts split out of ClientRecord."""

import pytest

from app.model.client_profile import ClientProfile
from app.model.review_status import ReviewStatus


def test_profile_holds_who_the_client_is():
    profile = ClientProfile("Daniel Tan", "Malaysian", "Singapore", 51)
    assert profile.to_dict() == {"name": "Daniel Tan", "nationality": "Malaysian",
                                 "country_of_residence": "Singapore", "age": 51}


def test_age_may_be_left_empty():
    assert ClientProfile("Daniel Tan", "Malaysian").age is None


@pytest.mark.parametrize("age", [17, 121, 51.5, "51", True])
def test_profile_rejects_an_age_that_cannot_be_right(age):
    with pytest.raises(ValueError):
        ClientProfile("Daniel Tan", "Malaysian", "Singapore", age)


def test_the_age_setter_validates_too():
    profile = ClientProfile("Daniel Tan", "Malaysian", "Singapore", 51)
    profile.age = 52
    assert profile.age == 52
    with pytest.raises(ValueError):
        profile.age = 5


def test_name_cannot_be_set_to_blank():
    profile = ClientProfile("Daniel Tan", "Malaysian")
    with pytest.raises(ValueError):
        profile.name = "   "
    profile.name = " Daniel Tan Wei Ming "
    assert profile.name == "Daniel Tan Wei Ming"


def test_a_new_review_status_is_empty_and_saves_nothing():
    status = ReviewStatus()
    assert status.outcome == ""
    assert status.to_dict() == {}


def test_update_records_one_assessment():
    status = ReviewStatus()
    status.update("RISKY", "Escalate to compliance", "2027-03-24", "2026-09-24", {"client_ref": "SOW-1"})
    assert status.to_dict() == {
        "forecasting_case": {"client_ref": "SOW-1"}, "outcome": "RISKY",
        "routing": "Escalate to compliance", "next_review_date": "2027-03-24",
        "last_assessed_on": "2026-09-24"}


def test_update_needs_an_outcome():
    with pytest.raises(ValueError):
        ReviewStatus().update("", "", "", "", {})
