#!/bin/sh
# Veritabanının ve fişlerin tarihli yedeğini alır.
# Kullanım: scripts/yedekle.sh [veri klasörü] [yedek klasörü]
#   örn. (docker-compose kurulumu):  scripts/yedekle.sh ./veri ./yedekler
set -eu
VERI="${1:-./veri}"
HEDEF="${2:-./yedekler}"
TARIH="$(date +%Y-%m-%d_%H%M)"
mkdir -p "$HEDEF"

# Uygulama çalışırken de tutarlı kopya almak için SQLite'ın kendi yedekleme komutu
python3 - "$VERI/defter.db" "$HEDEF/defter_$TARIH.db" <<'PY'
import sqlite3, sys
src, dst = sqlite3.connect(sys.argv[1]), sqlite3.connect(sys.argv[2])
with dst:
    src.backup(dst)
src.close(); dst.close()
PY

tar -czf "$HEDEF/fisler_$TARIH.tar.gz" -C "$VERI" fisler
echo "Yedek alındı: $HEDEF/defter_$TARIH.db ve $HEDEF/fisler_$TARIH.tar.gz"
