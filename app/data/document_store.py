"""DocumentStore: the supporting documents kept with the clients."""

import logging
import os
import shutil
import tempfile
import uuid

from app.data.document_reader_factory import DocumentReaderFactory
from app.data.json_repository import ROOT_DIR

logger = logging.getLogger(__name__)


class DocumentStore:
    """Keeps a local copy of every supporting document and reads documents for the AI.

    The store creates and owns its DocumentReaderFactory, and asks it for the right
    reader for each file. Only local copies are read; nothing comes from the cloud backup.
    """

    def __init__(self, folder: str = "data/documents", root: str = ROOT_DIR) -> None:
        self.__root: str = root
        self.__folder: str = folder if os.path.isabs(folder) else os.path.join(root, folder)
        self.__reader_factory: DocumentReaderFactory = DocumentReaderFactory()

    def upload(self, file_path: str) -> str | None:
        """Copy a file into the store. Returns its id (its path inside the project), or None."""
        if not file_path or not os.path.exists(file_path):
            return None
        destination = os.path.join(self.__folder, f"{uuid.uuid4().hex[:8]}_{os.path.basename(file_path)}")
        try:
            os.makedirs(self.__folder, exist_ok=True)
            shutil.copy2(file_path, destination)
        except OSError as error:
            logger.warning("DocumentStore.upload: copy failed for %s: %s", file_path, repr(error))
            return None
        return os.path.relpath(destination, self.__root).replace("\\", "/")   # forward slashes on any system

    def owns(self, file_id: str) -> bool:
        """True only for a document reference this store made: a path inside its own folder,
        or a cloud backup (GridFS) id. Anything else, such as "../../.env", is refused."""
        file_id = str(file_id or "")
        if len(file_id) == 24 and all(character in "0123456789abcdef" for character in file_id.lower()):
            return True
        if not file_id or ".." in file_id or "\\" in file_id or os.path.isabs(file_id):
            return False
        prefix = os.path.relpath(self.__folder, self.__root).replace("\\", "/") + "/"
        return file_id.startswith(prefix)

    def download(self, file_id: str, output_path: str) -> bool:
        """Copy a stored document out to output_path. file_id is the id upload() returned."""
        if not file_id:
            return False
        local = os.path.join(self.__root, file_id)
        if not os.path.isfile(local):
            return False
        try:
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            shutil.copy2(local, output_path)
            return True
        except OSError as error:
            logger.warning("DocumentStore.download: copy failed for %s: %s", file_id, repr(error))
            return False

    def read_all(self, entries: list[dict]) -> list[dict]:
        """Read every supporting document saved with a client, under the name it was uploaded as."""
        read = []
        for entry in entries or []:
            file_id = entry.get("file_path") or entry.get("file_id")     # the local copy first
            name = os.path.basename(str(entry.get("file_name") or file_id or "document"))
            folder = tempfile.mkdtemp()
            try:
                path = os.path.join(folder, name)
                if self.download(str(file_id or ""), path):
                    read.append(self.read_for_extraction(path, name))
                else:
                    read.append({"file_name": name, "kind": "error",
                                 "error": f"{name}: the saved copy couldn't be found."})
            finally:
                shutil.rmtree(folder, ignore_errors=True)
        return read

    def read_for_extraction(self, file_path: str, file_name: str | None = None) -> dict:
        """Read one file so the AI can pull client details out of it.
        Returns {"file_name", "kind", ...}; kind "error" if it could not be read."""
        name = file_name or os.path.basename(file_path)
        reader = self.__reader_factory.create(name)
        if reader is None:
            return {"file_name": name, "kind": "error",
                    "error": f"{name}: this file type can't be read (use PDF, Word, Excel, text or an image)."}
        try:
            return reader.read(file_path, name)
        except Exception as error:   # a damaged or password-protected file
            logger.warning("DocumentStore.read_for_extraction: %s: %s", name, repr(error))
            return {"file_name": name, "kind": "error",
                    "error": f"{name}: could not be read ({error.__class__.__name__})."}

    def list_folder(self, folder: str) -> list[str] | None:
        """The readable documents directly inside a folder (not sub-folders), sorted by name.
        Returns None if the folder doesn't exist. Hidden and Office temp files (~$...) are skipped."""
        folder = os.path.expanduser(folder or "")
        if not os.path.isdir(folder):
            return None
        readable = self.__reader_factory.supported_types()
        files = []
        for name in sorted(os.listdir(folder), key=str.lower):
            path = os.path.join(folder, name)
            if (os.path.isfile(path) and not name.startswith((".", "~$"))
                    and os.path.splitext(name)[1].lower() in readable):
                files.append(path)
        return files
