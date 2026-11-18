"""Shared set-up for the admin screen tests: an App in a temporary folder with a seeded audit log, the admin's
and an officer's sign-in, and a ConsoleUI that reads made-up answers and collects what it shows."""

from pathlib import Path

from app.application.app import App
from app.interface.console_ui import ConsoleUI
from app.model.account import Account
from tests.audit_files import seed_audit

WATCHED = [{"field": "claims.declared_net_worth", "before": 2000000, "after": 3500000}]
ALL_RULES = [
    ("client_created", "2026-11-01T02:00:00Z", "Shareen", "SOW-1", "ok", {}),                      # 1
    ("assessment_run", "2026-11-02T02:00:00Z", "Shareen", "SOW-1", "ok",
     {"outcome": "RISKY", "assessment_id": "A-1"}),                                                # 2
    ("client_edited", "2026-11-02T03:00:00Z", "Adrian", "SOW-1", "ok", {"changes": WATCHED}),      # 3 other (high)
    ("assessment_run", "2026-11-02T03:05:00Z", "Adrian", "SOW-1", "ok",
     {"outcome": "PASSED", "assessment_id": "A-2"}),                                               # 4 shop
    ("assessment_run", "2026-11-03T02:00:00Z", "Shareen", "SOW-1", "ok",
     {"outcome": "PASSED", "assessment_id": "A-3"}),                                               # 5
    ("assessment_run", "2026-11-04T02:00:00Z", "Shareen", "SOW-1", "ok",
     {"outcome": "PASSED", "assessment_id": "A-4"}),                                               # 6 repeat (4 runs)
    ("assessment_run", "2026-11-05T16:30:00Z", "Shareen", "SOW-1", "ok",
     {"outcome": "PASSED", "assessment_id": "A-5"}),                                               # 7 hours (00:30 SGT)
    ("assessment_failed", "2026-11-06T02:00:00Z", "Shareen", "SOW-1", "failed", {"step": "Crime scan"}),
    ("assessment_failed", "2026-11-06T02:10:00Z", "Shareen", "SOW-1", "failed", {"step": "Crime scan"}),
    ("data_unavailable", "2026-11-06T02:20:00Z", "Adrian", "", "failed", {"what": "client records"}),   # 8-10 spike
]
ADMIN_PASSWORD = "admin123"
OFFICER_PASSWORD = "officer123"


def make_app(tmp_path: Path, monkeypatch, seeded: bool = True, **options) -> App:
    """An App with no AI whose files are in tmp_path, with the ten audit lines above already in its log."""
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("MONGODB_URI", "")
    application = App(ai_caller=None, data_folder=str(tmp_path), **options)
    if seeded:
        seed_audit(tmp_path, ALL_RULES)
    return application


def account_named(application: App, role: str) -> Account:
    """The first configured account with this role ("admin" or "officer")."""
    return next(account for account in application.accounts() if account.role == role)


def screen(*typed: str):
    """(a ConsoleUI that reads the answers given, one per question, and keeps every line it shows, the list of
    those lines, the list of questions asked, the list of hidden questions asked). Running out of answers is
    a test failure, not a hang: the reader raises StopIteration."""
    waiting = iter(typed)
    shown: list[str] = []
    asked: list[str] = []
    hidden: list[str] = []

    def read(question: str = "") -> str:
        asked.append(question)
        return next(waiting)

    def secret(question: str = "") -> str:
        hidden.append(question)
        return next(waiting)

    return ConsoleUI(read=read, write=shown.append, secret=secret), shown, asked, hidden


def text_of(shown: list[str]) -> str:
    return "\n".join(shown)


def tamper(tmp_path: Path, row: int = 4) -> None:
    """Change one saved audit line (counting from 0) outside the app, so its hash no longer fits."""
    import json
    from tests.audit_files import audit_path
    rows = json.loads(Path(audit_path(tmp_path)).read_text(encoding="utf-8"))
    rows[row]["actor"] = "Someone else"
    Path(audit_path(tmp_path)).write_text(json.dumps(rows), encoding="utf-8")
