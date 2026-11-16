"""PayCalibrator: sets the forecast's pay to what his documents show."""

import copy

from app.logic.career_savings import CareerSavings
from app.logic.case_timeline import CaseTimeline
from app.logic.market_model import MarketModel


class PayCalibrator:
    """Where a tax notice or an employment letter shows what a job really paid, the AI's
    estimate for that job is moved to the documented figure. It is handed the
    CareerSavings (which knows how a pay row adds up) and the policy (how far a document
    may move an estimate).
    """

    def __init__(self, career_savings: CareerSavings | None = None, policy: dict | None = None) -> None:
        if career_savings is not None and not isinstance(career_savings, CareerSavings):
            raise ValueError(f"the career savings must be a CareerSavings (or None), not {type(career_savings).__name__}")
        if policy is not None and not isinstance(policy, dict):
            raise ValueError(f"the policy must be a dict (or None), not {type(policy).__name__}")
        self.__career_savings: CareerSavings = career_savings or CareerSavings()
        self.__policy: dict = policy or {}

    def calibrate(self, case: dict, forecast: dict, documented_pay: list[dict]) -> tuple[dict, list[dict]]:
        """Use the pay his documents show (tax notices, employment letter) instead of the AI's guess.

        For each job with documented years, every year of that job's forecast pay is scaled by
        documented / AI-typical over those years (the current job's future pay too), so the honest
        story is built on his real pay. The AI never sees these figures; only this arithmetic does.
        Returns (adjusted forecast copy, one row per adjusted job)."""
        policy = self.__policy
        settings = policy["verdict"]["pay_calibration"]
        documented = {row["year"]: row for row in documented_pay or []}
        if not documented:
            return forecast, []
        forecast = copy.deepcopy(forecast)
        _, end = CaseTimeline(case).career_years()
        jobs = CaseTimeline(case).positions()
        adjusted = []
        for position in forecast["earnings"]["positions"]:
            index = position["position_index"]
            if not 0 <= index < len(jobs):
                continue
            job = jobs[index]
            first, last = int(job["start_year"]), CaseTimeline(case).position_end(job)
            years = [row for row in position["yearly"] if row["year"] in documented and first <= row["year"] <= last]
            guessed = sum(self.__career_savings.pay_total(row, "typical") for row in years)
            actual = sum(documented[row["year"]]["amount"] for row in years)
            if not years or guessed <= 0:
                continue
            ratio = min(max(actual / guessed, 1 / settings["max_ratio"]), settings["max_ratio"])
            if abs(ratio - 1) < settings["min_change"]:
                continue
            for row in position["yearly"]:
                for part in ("base_pay", "bonus", "equity_or_profit_share"):
                    row[part] = {k: v * ratio for k, v in row[part].items()}
            if job.get("end_year") in (None, ""):
                for row in forecast["earnings"]["future_pay"]["yearly"]:
                    for scenario in MarketModel.SCENARIOS:
                        for part in ("base_pay", "bonus", "equity_or_profit_share"):
                            row[scenario][part] = {k: v * ratio for k, v in row[scenario][part].items()}
            shown = years[-1]["year"]
            adjusted.append({"position_index": index, "job": f"{job.get('occupation')} at {job.get('employer_name')}",
                             "ratio": round(ratio, 2), "year": shown, "ai_pay": round(self.__career_savings.pay_total(
                                 next(r for r in years if r["year"] == shown), "typical") / ratio),
                             "documented_pay": documented[shown]["amount"],
                             "source_file": documented[shown].get("source_file")})
        return forecast, adjusted
