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
