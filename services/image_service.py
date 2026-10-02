#that file just for resizing image

import base64
import io
import os
import uuid

from PIL import Image
from werkzeug.utils import secure_filename

from config import ALLOWED_EXTENSIONS, MAX_IMAGE_DIM, UPLOAD_DIR


def allowed_file(filename: str) -> bool:
    #Return True when the file extension is an accepted image type
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def image_to_base64(path: str) -> str:
    #Load an image, downscale it and return a base64 encoded JPEG string
    with Image.open(path) as img:
        img = img.convert("RGB")
        img.thumbnail((MAX_IMAGE_DIM, MAX_IMAGE_DIM))
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=85)
        return base64.b64encode(buffer.getvalue()).decode("ascii")


def save_uploads(files, labels) -> list:
    """
    Save uploaded files to the upload folder.

    Returns a list of (label, path) tuples, in the same order as the input.
    If a label is missing, the file's own name (without extension) is used.
    """
    saved = []

    # Pad labels if the browser did not send one per file
    labels = list(labels) + [""] * max(0, len(files) - len(labels))

    for file, label in zip(files, labels):
        if not allowed_file(file.filename):
            continue

        clean_label = (label or "").strip()
        if not clean_label:
            clean_label = os.path.splitext(file.filename)[0]

        safe_name = secure_filename(file.filename)
        unique_name = f"{uuid.uuid4().hex}_{safe_name}"
        path = os.path.join(UPLOAD_DIR, unique_name)
        file.save(path)
        saved.append((clean_label, path))

    return saved


def cleanup_files(items) -> None:
    #Delete temporary uploaded files ->if finish
    for item in items:
        path = item[1] if isinstance(item, tuple) else item
        try:
            os.remove(path)
        except OSError:
            pass