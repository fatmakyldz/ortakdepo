"""Kapsayıcının başlangıç betiği.

Bağlanan veri klasörü (Docker bind mount, Render diski, Railway volume) çoğu zaman
root'a ait gelir. Bu betik root olarak başlar, klasörü uygulama kullanıcısına verir,
sonra yetkiyi bırakıp uygulamayı o kullanıcıyla çalıştırır. Böylece elle `chown`
gerekmez ve uygulama root olarak çalışmaz.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_UID = int(os.environ.get("APP_UID", "10001"))
DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
PORT = os.environ.get("PORT", "8000")


def give_ownership(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if path.stat().st_uid == APP_UID:
        return  # daha önce verilmiş; büyük klasörü her açılışta dolaşmayalım
    for root, dirs, files in os.walk(path):
        for name in dirs + files:
            try:
                os.chown(os.path.join(root, name), APP_UID, APP_UID, follow_symlinks=False)
            except OSError:
                pass
    os.chown(path, APP_UID, APP_UID)


def main() -> None:
    if os.getuid() == 0:
        try:
            give_ownership(DATA_DIR)
        except OSError as exc:
            print(f"Uyarı: {DATA_DIR} sahipliği ayarlanamadı: {exc}", file=sys.stderr)
        os.setgroups([])
        os.setgid(APP_UID)
        os.setuid(APP_UID)
    os.environ.setdefault("HOME", "/tmp")
    os.execvp("uvicorn", [
        "uvicorn", "app.main:app",
        "--host", "0.0.0.0", "--port", PORT,
        "--proxy-headers", "--forwarded-allow-ips", "*",
    ])


if __name__ == "__main__":
    main()
