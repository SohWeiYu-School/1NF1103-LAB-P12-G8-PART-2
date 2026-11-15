"""Tests for CrimeScan.verify_research: the trusted research reports, as ResearchReport objects."""

from app.logic.crime_scan import CrimeScan
from app.model.research_report import ResearchReport


def verify_research(research, policy):
    """(the kept ResearchReports, the warnings), as these tests have always used it."""
    scan = CrimeScan(policy)
    reports = scan.verify_research(research)
    return reports, scan.warnings()


def _sample_policy(trusted=None):
    return {
        "trusted_sources": trusted or ["fatf-gafi.org", "mas.gov.sg"],
    }


def _sample_report(report_id, url, org="FATF", year=2020):
    return {
        "report_id": report_id,
        "url": url,
        "organisation": org,
        "year": year,
        "title": "Test Report",
        "summary": "Summary",
        "excerpts": ["Excerpt one.", "Excerpt two."],
    }


def _sample_research(reports, api_sources=None):
    if api_sources is None:
        api_sources = [{"url": r["url"]} for r in reports]
    return {
        "reports": reports,
        "api_sources": api_sources,
        "retrieved_at": "2025-01-01T00:00:00Z",
        "model": "test-model",
    }


# ---------------------------------------------------------------------------
# Test 1: URL not in api_sources → removed + warning
# ---------------------------------------------------------------------------

def test_url_not_in_api_sources_removed():
    report = _sample_report("R1", "https://fatf-gafi.org/report.pdf")
    research = _sample_research([report], api_sources=[])  # empty api_sources
    policy = _sample_policy()

    reports, warnings = verify_research(research, policy)

    assert reports == []
    assert any("R1" in w and "web search" in w for w in warnings)


# ---------------------------------------------------------------------------
# Test 2: Domain not trusted → removed + warning
# ---------------------------------------------------------------------------

def test_untrusted_domain_removed():
    report = _sample_report("R1", "https://untrusted-site.com/report.pdf")
    research = _sample_research([report])
    policy = _sample_policy()

    reports, warnings = verify_research(research, policy)

    assert reports == []
    assert any("R1" in w and "trusted" in w for w in warnings)


# ---------------------------------------------------------------------------
# Test 3: Duplicate URL → second removed
# ---------------------------------------------------------------------------

def test_duplicate_url_second_removed():
    url = "https://fatf-gafi.org/report.pdf"
    r1 = _sample_report("R1", url)
    r2 = _sample_report("R2", url)
    research = _sample_research([r1, r2], api_sources=[{"url": url}])
    policy = _sample_policy()

    reports, warnings = verify_research(research, policy)

    assert len(reports) == 1
    assert any("R2" in w and "duplicate" in w for w in warnings)


# ---------------------------------------------------------------------------
# Test 4: Original IDs are preserved after filtering (gaps are fine)
# ---------------------------------------------------------------------------

def test_original_ids_preserved_after_filtering():
    r1 = _sample_report("R1", "https://fatf-gafi.org/r1.pdf")
    r2 = _sample_report("R2", "https://untrusted.com/r2.pdf")  # will be removed (untrusted)
    r3 = _sample_report("R3", "https://mas.gov.sg/r3.pdf")
    research = _sample_research(
        [r1, r2, r3],
        api_sources=[
            {"url": "https://fatf-gafi.org/r1.pdf"},
            {"url": "https://untrusted.com/r2.pdf"},
            {"url": "https://mas.gov.sg/r3.pdf"},
        ],
    )
    policy = _sample_policy()

    reports, warnings = verify_research(research, policy)

    ids = [r.report_id for r in reports]
    # R2 removed (untrusted), R1 and R3 survive with their original IDs (gap is intentional)
    assert ids == ["R1", "R3"]


# ---------------------------------------------------------------------------
# Test 5: All valid → nothing removed, no warnings
# ---------------------------------------------------------------------------

def test_all_valid_nothing_removed():
    r1 = _sample_report("R1", "https://fatf-gafi.org/r1.pdf")
    r2 = _sample_report("R2", "https://mas.gov.sg/r2.pdf")
    research = _sample_research([r1, r2])
    policy = _sample_policy()

    reports, warnings = verify_research(research, policy)

    assert len(reports) == 2
    assert warnings == []


# ---------------------------------------------------------------------------
# Test 6: Empty reports → empty result, no warnings
# ---------------------------------------------------------------------------

def test_empty_reports():
    research = _sample_research([], api_sources=[])
    policy = _sample_policy()

    reports, warnings = verify_research(research, policy)

    assert reports == []
    assert warnings == []


# ---------------------------------------------------------------------------
# Test 7: Subdomain www.fatf-gafi.org matches trusted fatf-gafi.org
# ---------------------------------------------------------------------------

def test_subdomain_matches_trusted():
    report = _sample_report("R1", "https://www.fatf-gafi.org/report.pdf")
    research = _sample_research([report])
    policy = _sample_policy()

    reports, warnings = verify_research(research, policy)

    assert len(reports) == 1
    assert warnings == []


# ---------------------------------------------------------------------------
# Test 8: The kept reports are ResearchReport objects with every field
# ---------------------------------------------------------------------------

def test_kept_reports_are_research_report_objects():
    report = _sample_report("R1", "https://www.fatf-gafi.org/report.pdf")
    reports, _ = verify_research(_sample_research([report]), _sample_policy())
    assert all(isinstance(kept, ResearchReport) for kept in reports)
    kept = reports[0]
    assert (kept.report_id, kept.url, kept.organisation, kept.year, kept.title) == (
        "R1", "https://www.fatf-gafi.org/report.pdf", "FATF", 2020, "Test Report")
    assert kept.excerpts == ["Excerpt one.", "Excerpt two."]
    assert kept.retrieved_at == "2025-01-01T00:00:00Z"        # the age check measures from it


# ---------------------------------------------------------------------------
# Test 9: A report that cannot be read is removed with a warning, not a crash
# ---------------------------------------------------------------------------

def test_unreadable_report_removed_not_crashed():
    good = _sample_report("R1", "https://fatf-gafi.org/r1.pdf")
    broken = {**_sample_report("R2", "https://mas.gov.sg/r2.pdf"), "excerpts": "one long excerpt"}
    research = _sample_research([good, broken, "not a report"], api_sources=[{"url": good["url"]}, {"url": broken["url"]}])
    reports, warnings = verify_research(research, _sample_policy())
    assert [r.report_id for r in reports] == ["R1"]
    assert any("R2" in w and "could not be read" in w for w in warnings)
    assert any("?" in w and "could not be read" in w for w in warnings)


# ---------------------------------------------------------------------------
# Test 10: warnings() only describes the last call
# ---------------------------------------------------------------------------

def test_warnings_are_those_of_the_last_call():
    scan = CrimeScan(_sample_policy())
    scan.verify_research(_sample_research([_sample_report("R1", "https://untrusted.com/x")]))
    assert scan.warnings()
    scan.verify_research(_sample_research([]))
    assert scan.warnings() == []
