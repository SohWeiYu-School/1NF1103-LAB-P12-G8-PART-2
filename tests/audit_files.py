"""Make the audit log unwritable in a test through the file system, without patching anything."""

import os


def audit_path(tmp_path) -> str:
    """Where an App built with data_folder=str(tmp_path) keeps its audit log."""
    return str(tmp_path / "local database" / "audit_log.json")


def break_audit(tmp_path) -> None:
    """Put a folder where the audit file should be (the log written so far is removed): it can then be
    neither read nor written."""
    path = audit_path(tmp_path)
    if os.path.isfile(path):
        os.remove(path)
    os.makedirs(path)


def fix_audit(tmp_path) -> None:
    """Take the folder away again: the log is then missing, which is an empty log."""
    os.rmdir(audit_path(tmp_path))


def seed_audit(tmp_path, lines) -> None:
    """Write audit lines with the times the test chooses, signed with the test key, as App would write them.
    Each line is (action, time as 2026-11-10T02:00:00Z, actor, client reference, result, details)."""
    from app.data.audit_repository import AuditRepository
    from app.model.audit_event import AuditEvent
    repository = AuditRepository(audit_path(tmp_path), key=os.getenv("AUDIT_KEY", ""))
    for action, at, actor, client, result, details in lines:
        assert repository.save(AuditEvent(at=at, actor=actor, action=action, client_ref=client, result=result,
                                          details=details).to_dict())
