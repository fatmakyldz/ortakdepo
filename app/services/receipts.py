"""Fiş / dekont dosyalarının kaydı.

Fotoğraflar yeniden kodlanır: telefonun 8-10 MB'lık çekimi ~300 KB'a iner,
yön bilgisi düzeltilir, konum gibi EXIF verileri atılır.
"""
from __future__ import annotations

import io
import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError

from ..config import settings
from ..timeutil import today

try:  # iPhone'un HEIC fotoğrafları için; kurulu değilse JPG/PNG/WEBP ile devam edilir
    import pillow_heif

    pillow_heif.register_heif_opener()
except Exception:  # pragma: no cover
    pass

MAX_SIDE = 2000
THUMB_SIDE = 480
Image.MAX_IMAGE_PIXELS = 60_000_000


class ReceiptError(ValueError):
    pass


@dataclass
class SavedFile:
    path: str
    thumb_path: str | None
    content_type: str
    size: int
    original_name: str


def _target_dir() -> tuple[Path, str]:
    t = today()
    rel = f"{t.year}/{t.month:02d}"
    full = settings.upload_dir / rel
    full.mkdir(parents=True, exist_ok=True)
    return full, rel


def save_upload(upload: UploadFile) -> SavedFile:
    limit = settings.max_upload_mb * 1024 * 1024
    raw = upload.file.read(limit + 1)
    name = " ".join((upload.filename or "fis").split())[:60]
    if not raw:
        raise ReceiptError(f"“{name}” boş bir dosya.")
    if len(raw) > limit:
        raise ReceiptError(f"“{name}” {settings.max_upload_mb} MB sınırını aşıyor.")

    folder, rel = _target_dir()
    key = uuid.uuid4().hex

    if raw[:5] == b"%PDF-":
        (folder / f"{key}.pdf").write_bytes(raw)
        return SavedFile(f"{rel}/{key}.pdf", None, "application/pdf", len(raw), name)

    try:
        img = Image.open(io.BytesIO(raw))
        if img.format == "JPEG":
            # JPEG doğrudan küçültülmüş olarak açılır: 12 MP'lik fotoğraf belleğe tam boy
            # (36 MB) yerine yarı ya da çeyrek boy gelir. Küçük sunucuda bellek için önemli.
            scale = max(img.size) / MAX_SIDE
            if scale > 1:
                img.draft("RGB", (int(img.width / scale), int(img.height / scale)))
        img.load()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise ReceiptError(
            f"“{name}” okunamadı. Fotoğraf (JPG, PNG, WEBP, HEIC) ya da PDF yükleyin."
        ) from None

    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "L"):
        # Saydam alanlar beyaz zemine oturtulur
        rgba = img.convert("RGBA")
        bg = Image.new("RGB", rgba.size, (255, 255, 255))
        bg.paste(rgba, mask=rgba.split()[-1])
        img = bg
    del raw  # yüklenen ham dosya artık gerekmiyor; belleği erken bırak
    img.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
    out = folder / f"{key}.jpg"
    img.save(out, "JPEG", quality=82, optimize=True)

    thumb = img.copy()
    thumb.thumbnail((THUMB_SIDE, THUMB_SIDE), Image.LANCZOS)
    thumb.save(folder / f"{key}_k.jpg", "JPEG", quality=76, optimize=True)

    return SavedFile(f"{rel}/{key}.jpg", f"{rel}/{key}_k.jpg", "image/jpeg", out.stat().st_size, name)


def resolve(rel_path: str) -> Path | None:
    """Göreli yolu yükleme klasörü içinde güvenli biçimde çözer."""
    base = settings.upload_dir.resolve()
    full = (base / rel_path).resolve()
    if base not in full.parents or not full.is_file():
        return None
    return full


def delete_files(*rel_paths: str | None) -> None:
    for rel in rel_paths:
        if not rel:
            continue
        full = resolve(rel)
        if full:
            try:
                full.unlink()
            except OSError:
                pass
