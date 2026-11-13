"""Feature: what the four parts of an assessment share."""

import pytest

from app.logic.feature import Feature
from app.model.check import Check


class _Sample(Feature):
    """A small feature for these tests."""

    NAME = "sample"

    def run(self, case: dict, ai_data: dict) -> dict:
        self._results = {"limit": self._policy.get("limit"), "worth": case["claims"]["declared_net_worth"]}
        return self._results

    def checks(self, context: dict) -> list[Check]:
        over = self._results["worth"] > self._results["limit"]
        return [self._check("OVER_LIMIT", "Net worth limit", "wealth", "failed" if over else "passed",
                            "Over the limit." if over else "Within the limit.")]


CASE = {"claims": {"declared_net_worth": 500, "biggest_wealth_jump": 3_000_000, "wealth_jump_years": 2.4}}


def test_the_abstract_feature_cannot_be_created():
    with pytest.raises(TypeError):
        Feature()


def test_a_child_that_leaves_out_checks_cannot_be_created():
    class _Half(Feature):
        def run(self, case, ai_data):
            return {}
    with pytest.raises(TypeError):
        _Half()


def test_run_uses_the_policy_and_keeps_its_results():
    feature = _Sample({"limit": 100})
    assert feature.run(CASE, {}) == {"limit": 100, "worth": 500}


def test_checks_are_stamped_with_the_features_name():
    feature = _Sample({"limit": 100})
    feature.run(CASE, {})
    check = feature.checks({})[0]
    assert isinstance(check, Check)
    assert (check.feature, check.check, check.status) == ("sample", "OVER_LIMIT", "failed")


def test_two_features_can_be_used_the_same_way():
    results = []
    for feature in (_Sample({"limit": 100}), _Sample({"limit": 1000})):
        feature.run(CASE, {})
        results.append(feature.checks({})[0].status)
    assert results == ["failed", "passed"]


def test_jump_years_reads_the_declared_wealth_jump():
    assert _Sample()._jump_years(CASE) == (3_000_000.0, 2)


@pytest.mark.parametrize("claims", [{}, {"biggest_wealth_jump": 0, "wealth_jump_years": 2},
                                    {"biggest_wealth_jump": 5, "wealth_jump_years": None},
                                    {"biggest_wealth_jump": "5", "wealth_jump_years": 2}])
def test_jump_years_is_empty_when_no_usable_jump_was_declared(claims):
    assert _Sample()._jump_years({"claims": claims}) == (None, None)


def test_a_jump_over_part_of_a_year_counts_as_one_year():
    assert _Sample()._jump_years({"claims": {"biggest_wealth_jump": 5, "wealth_jump_years": 0.3}}) == (5.0, 1)
