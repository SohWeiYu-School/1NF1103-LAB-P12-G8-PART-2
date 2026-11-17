"""ResearchAI: only industry and country are sent; the reply is trimmed, numbered and cleaned.
The AI replies are hard-coded; no network."""

import json
from types import SimpleNamespace

from app.ai.research_ai import ResearchAI

CASE = {"client_ref": "ID-2233", "occupation": "Chief Operating Officer",
        "industry": "Maritime shipping and freight forwarding", "age": 51, "career_start_year": 1998,
        "country": "Singapore", "country_of_residence": "Singapore", "declaration_text": "Some text."}
DOMAINS = ["fatf-gafi.org", "mas.gov.sg"]


def _report(title="Test Report", **changes):
    report = {"organisation": "FATF", "title": title, "year": 2020, "url": "https://www.fatf-gafi.org/test-report",
              "excerpts": ["Excerpt from the report."],
              "summary": ["Over-invoicing of goods to move funds.", "Use of shell companies."]}
    report.update(changes)
    return report


def _openai_response(citations=(), searched=()):
    """A made-up OpenAI web-search response: pages opened by the search, and links cited in the reply."""
    output = []
    if searched:
        output.append(SimpleNamespace(type="web_search_call", action=SimpleNamespace(
            sources=[SimpleNamespace(url=url) for url in searched])))
    annotations = [SimpleNamespace(type="url_citation", url=url, title=title) for url, title in citations]
    output.append(SimpleNamespace(type="message", content=[
        SimpleNamespace(type="output_text", annotations=annotations)]))
    return SimpleNamespace(output=output)


class _Search:
    """A made-up AI caller for a web search: one hard-coded reply and one hard-coded response object."""

    def __init__(self, reports, response=None):
        self.reply = None if reports is None else json.dumps({"reports": reports})
        self.response = response if response is not None else _openai_response()
        self.prompts, self.options = [], []

    def __call__(self, prompt, schema, options):
        self.prompts.append(prompt)
        self.options.append(dict(options))
        options["raw_response"] = self.response
        return self.reply


def _run(caller, case=CASE, **limits):
    service = ResearchAI("fake", caller, "gpt-test", 0.0, **limits)
    return service.run({"case": case, "domains": DOMAINS}), service.warnings()


def test_only_industry_and_country_are_sent():
    caller = _Search([_report()])
    _run(caller)
    prompt = caller.prompts[0]
    assert "Maritime shipping" in prompt and "Singapore" in prompt
    assert "Chief Operating Officer" not in prompt
    assert "ID-2233" not in prompt


def test_country_falls_back_to_the_country_of_residence():
    case = {key: value for key, value in CASE.items() if key != "country"}
    case["country_of_residence"] = "Malaysia"
    caller = _Search([_report()])
    _run(caller, case)
    assert '"country": "Malaysia"' in caller.prompts[0]


def test_the_search_is_limited_to_the_trusted_sites():
    caller = _Search([_report()])
    _run(caller)
    assert caller.options[0]["web_search"] is True
    assert caller.options[0]["domains"] == DOMAINS
    assert "fatf-gafi.org, mas.gov.sg" in caller.prompts[0]


def test_reports_are_numbered_by_code():
    result, _ = _run(_Search([_report("A"), _report("B")]))
    assert [report["report_id"] for report in result["reports"]] == ["R1", "R2"]


def test_nine_reports_are_cut_to_eight_with_a_warning():
    result, warnings = _run(_Search([_report(f"Report {number}") for number in range(9)]))
    assert len(result["reports"]) == 8
    assert any("kept first 8" in warning for warning in warnings)


def test_excerpts_are_cut_to_the_limit():
    result, _ = _run(_Search([_report(excerpts=[f"Excerpt {n}" for n in range(7)])]), max_excerpts=3)
    assert len(result["reports"][0]["excerpts"]) == 3


def test_a_year_given_as_text_becomes_a_number():
    result, _ = _run(_Search([_report(year="2020")]))
    assert result["reports"][0]["year"] == 2020


def test_quote_marks_around_excerpts_are_removed():
    excerpts = ["“This is a quoted excerpt.”", "‘Another excerpt’", '"Double quoted"']
    result, _ = _run(_Search([_report(excerpts=excerpts)]))
    assert result["reports"][0]["excerpts"] == ["This is a quoted excerpt.", "Another excerpt", "Double quoted"]


def test_sources_come_from_the_links_cited_in_the_reply():
    response = _openai_response(citations=[("https://www.fatf-gafi.org/page1", "FATF Page 1"),
                                           ("https://www.mas.gov.sg/page2", "MAS Page 2")])
    result, warnings = _run(_Search([_report()], response))
    assert result["api_sources"] == [{"url": "https://www.fatf-gafi.org/page1", "title": "FATF Page 1"},
                                     {"url": "https://www.mas.gov.sg/page2", "title": "MAS Page 2"}]
    assert warnings == []


def test_sources_come_from_the_pages_the_search_opened():
    response = _openai_response(searched=["https://www.fatf-gafi.org/search-1", "https://www.mas.gov.sg/search-2"])
    result, _ = _run(_Search([_report()], response))
    assert [source["url"] for source in result["api_sources"]] == [
        "https://www.fatf-gafi.org/search-1", "https://www.mas.gov.sg/search-2"]


def test_the_same_page_is_listed_once():
    response = _openai_response(citations=[("https://www.fatf-gafi.org/page1", "FATF"),
                                           ("https://www.fatf-gafi.org/page1", "FATF duplicate")])
    result, _ = _run(_Search([_report()], response))
    assert len(result["api_sources"]) == 1


def test_no_sources_gives_a_warning():
    result, warnings = _run(_Search([_report()]))
    assert result["api_sources"] == []
    assert any("no sources" in warning.lower() for warning in warnings)


def test_a_gemini_reply_with_no_search_details_uses_the_report_links():
    gemini_response = SimpleNamespace(candidates=[])
    result, warnings = _run(_Search([_report()], gemini_response))
    assert result["api_sources"] == [{"url": "https://www.fatf-gafi.org/test-report", "title": "Test Report"}]
    assert warnings == []


def test_the_time_and_the_model_are_recorded():
    result, _ = _run(_Search([_report()]))
    assert result["model"] == "gpt-test"
    assert result["retrieved_at"].startswith("20")


def test_a_failed_search_gives_none_and_is_not_retried():
    caller = _Search(None)
    result, warnings = _run(caller)
    assert result is None
    assert warnings == []
    assert len(caller.prompts) == 1


def test_a_report_with_no_link_is_a_malformed_reply():
    report = _report()
    del report["url"]
    result, _ = _run(_Search([report]))
    assert result is None


def test_a_saved_reply_is_reused_for_the_same_question_even_with_the_fields_added_after_the_reply():
    saved = {}
    source = {"case": CASE, "domains": DOMAINS, "saved_replies": saved}
    first = ResearchAI("fake", _Search([_report()]), "gpt-test", 0.0).run(source)
    assert first["reports"][0]["report_id"] == "R1" and first["model"] == "gpt-test"
    second = _Search([_report()])
    assert ResearchAI("fake", second, "gpt-test", 0.0).run(source) == first
    assert second.prompts == []
