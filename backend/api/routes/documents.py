"""Serve the original source PDFs so the UI can open a TdR.

Files are read from the raw data directory. Only the basename is used and the
file must actually exist there, which prevents path-traversal outside the
folder. Served inline (no attachment header) so the browser opens the PDF in a
new tab rather than downloading it.
"""

import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from backend.core import config

router = APIRouter(prefix="/documents", tags=["documents"])

RAW_DIR = os.path.join(config.DATA_DIR, "raw")


@router.get("/{filename:path}")
def get_document(filename: str):
    # Collapse to a bare filename to block ../ traversal, then require it to
    # be a real file in the raw directory.
    safe = os.path.basename(filename)
    path = os.path.join(RAW_DIR, safe)
    if not safe or not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Document introuvable.")
    return FileResponse(path, media_type="application/pdf")
