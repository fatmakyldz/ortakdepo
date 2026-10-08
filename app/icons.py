"""Arayüz ve kategori simgeleri: 24×24 çizgi simgeler, satır içi SVG olarak basılır."""
from __future__ import annotations

from markupsafe import Markup

_P = {
    # --- arayüz
    "bugun": '<path d="M4 11l8-7 8 7"/><path d="M6 10v9h12v-9"/>',
    "kayitlar": '<path d="M9 7h11M9 12h11M9 17h11"/><path d="M4.500 7h.010M4.500 12h.010M4.500 17h.010"/>',
    "sabit": '<rect x="4" y="5" width="16" height="15" rx="3"/><path d="M4 10h16M9 3v4M15 3v4"/>',
    "ortaklar": '<circle cx="9" cy="8.500" r="3.200"/><path d="M3 20c.500-3.400 2.800-5.200 6-5.200s5.500 1.800 6 5.200"/>'
                '<path d="M16 5.600a3.200 3.200 0 010 5.800M18 15.300c1.700.700 2.700 2.300 3 4.700"/>',
    "rapor": '<path d="M5 20v-8M12 20V4M19 20v-5"/>',
    "ayarlar": '<path d="M4 7h9M19 7h1M4 17h1M11 17h9"/><circle cx="16" cy="7" r="2.500"/><circle cx="8" cy="17" r="2.500"/>',
    "arti": '<path d="M12 5v14M5 12h14"/>',
    "eksi": '<path d="M5 12h14"/>',
    "sol": '<path d="M15 5l-7 7 7 7"/>',
    "sag": '<path d="M9 5l7 7-7 7"/>',
    "atac": '<path d="M20 11.500l-8 8a5 5 0 01-7-7l8.500-8.500a3.500 3.500 0 015 5L10 17.500a2 2 0 01-3-3L14.500 7"/>',
    "indir": '<path d="M12 4v11M7 11l5 5 5-5M5 20h14"/>',
    "gunes": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.900 4.900l1.400 1.400M17.700 17.700l1.400 1.400'
             'M2 12h2M20 12h2M4.900 19.100l1.400-1.400M17.700 6.300l1.400-1.400"/>',
    "ay": '<path d="M20 14.500A8.500 8.500 0 019.500 4 8.500 8.500 0 1020 14.500z"/>',
    "cikis": '<path d="M10 4H6a2 2 0 00-2 2v12a2 2 0 002 2h4"/><path d="M15 8l4 4-4 4M19 12H9"/>',
    "uyari": '<path d="M12 4l9 16H3z"/><path d="M12 10v4M12 17h.010"/>',
    "tik": '<path d="M5 12.500l4.500 4.500L19 7.500"/>',
    # --- kategoriler
    "yakit": '<rect x="4" y="4" width="10" height="16" rx="2"/><path d="M4 10h10"/>'
             '<path d="M14 9h1.500a2 2 0 012 2v5.500a1.500 1.500 0 003 0V8.500L17.500 5.500"/>',
    "isci": '<path d="M4 17v-1a8 8 0 0116 0v1"/><path d="M2.500 17.500h19"/><path d="M10 8.300v3.700M14 8.300v3.700"/>',
    "yemek": '<path d="M5 3v5a2 2 0 004 0V3M7 3v18"/><path d="M17 21v-7h-3V9c0-2.800 1.200-4.800 3-6v11"/>',
    "anahtar": '<path d="M14.700 5.300a4.200 4.200 0 00-5.400 5.400L4 16l4 4 5.300-5.300a4.200 4.200 0 005.400-5.400'
               'l-2.700 2.700-2.500-.500-.500-2.500z"/>',
    "belge": '<path d="M7 3h7l4 4v14H7z"/><path d="M14 3v4h4M10 12h5M10 16h5"/>',
    "fis": '<path d="M6 3h12v18l-3-2-3 2-3-2-3 2z"/><path d="M9 8h6M9 12h6"/>',
    "diger": '<circle cx="6" cy="12" r="1.300"/><circle cx="12" cy="12" r="1.300"/><circle cx="18" cy="12" r="1.300"/>',
    "canta": '<rect x="3" y="7" width="18" height="13" rx="2.500"/><path d="M9 7V5.500A1.500 1.500 0 0110.500 4h3A1.500 1.500 0 0115 5.500V7M3 13h18"/>',
    "para": '<rect x="3" y="6" width="18" height="12" rx="2.500"/><circle cx="12" cy="12" r="2.500"/><path d="M6.500 10v4M17.500 10v4"/>',
    "kamyon": '<path d="M3 6h10v10H3zM13 10h4l3 3v3h-7z"/><circle cx="7" cy="17.500" r="1.800"/><circle cx="17" cy="17.500" r="1.800"/>',
    "ev": '<path d="M4 20V9.500l8-5.500 8 5.500V20z"/><path d="M10 20v-6h4v6"/>',
    "kalkan": '<path d="M12 3l7 3v5c0 4.500-3 8-7 10-4-2-7-5.500-7-10V6z"/>',
    "yuzde": '<path d="M19 5L5 19"/><circle cx="7" cy="7" r="2.500"/><circle cx="17" cy="17" r="2.500"/>',
    "telefon": '<rect x="7" y="3" width="10" height="18" rx="2.500"/><path d="M11 17.500h2"/>',
    "yol": '<path d="M8 3L5 21M16 3l3 18M12 5v3M12 11v3M12 17v3"/>',
    "sepet": '<path d="M3 4h2l2.500 11h10L20 7H6.500"/><circle cx="9" cy="19" r="1.500"/><circle cx="17" cy="19" r="1.500"/>',
    "simsek": '<path d="M13 3L5 14h6l-1 7 8-11h-6z"/>',
    "damla": '<path d="M12 3c3.500 4.500 6 7.500 6 11a6 6 0 01-12 0c0-3.500 2.500-6.500 6-11z"/>',
    "etiket": '<path d="M3 12V4h8l10 10-8 8z"/><circle cx="7.500" cy="8.500" r="1.200"/>',
}

# Ayarlar'da kategoriye seçilebilen simgeler (ad -> görünen ad)
CATEGORY_ICONS: dict[str, str] = {
    "yakit": "Yakıt", "isci": "İşçilik", "yemek": "Yemek", "anahtar": "Bakım", "belge": "Sözleşme",
    "fis": "Fiş", "kamyon": "Araç", "ev": "Kira", "kalkan": "Sigorta", "yuzde": "Vergi",
    "telefon": "Telefon", "yol": "Yol", "sepet": "Alışveriş", "simsek": "Elektrik", "damla": "Su",
    "canta": "İş", "para": "Para", "etiket": "Etiket", "diger": "Diğer",
}

_KEYWORDS: list[tuple[tuple[str, ...], str]] = [
    (("yakıt", "yakit", "mazot", "benzin", "akaryak", "motorin"), "yakit"),
    (("yevmiye", "işçi", "isci", "maaş", "maas", "personel", "operatör", "usta"), "isci"),
    (("yemek", "kahvaltı", "lokanta", "çay"), "yemek"),
    (("bakım", "bakim", "onarım", "tamir", "servis", "lastik", "yedek", "parça"), "anahtar"),
    (("leasing", "kredi", "taksit", "sözleşme"), "belge"),
    (("kira", "depo", "ofis"), "ev"),
    (("sigorta", "kasko"), "kalkan"),
    (("vergi", "kdv", "sgk", "muhasebe", "stopaj"), "yuzde"),
    (("telefon", "internet", "gsm"), "telefon"),
    (("otoyol", "köprü", "hgs", "ogs", "otopark", "yol"), "yol"),
    (("nakliye", "kamyon", "araç", "arac", "makine"), "kamyon"),
    (("elektrik",), "simsek"),
    (("su ", "su faturası"), "damla"),
    (("market", "malzeme", "alışveriş"), "sepet"),
    (("iş geliri", "hakediş", "kiralama", "hizmet"), "canta"),
    (("gelir", "tahsilat", "nakit"), "para"),
    (("diğer", "diger"), "diger"),
    (("ek gider", "masraf"), "fis"),
]


def guess_icon(name: str, kind: str = "gider") -> str:
    """Kategori adından uygun simgeyi tahmin eder; bulamazsa genel etiket."""
    key = (name or "").replace("I", "ı").replace("İ", "i").lower() + " "
    for words, icon in _KEYWORDS:
        if any(w in key for w in words):
            return icon
    return "para" if kind == "gelir" else "etiket"


def svg(name: str | None, cls: str = "") -> Markup:
    """Jinja'dan çağrılır: {{ ikon("yakit") }}. Bilinmeyen ad genel etikete düşer."""
    body = _P.get(name or "", _P["etiket"])
    attr = f' class="{cls}"' if cls.replace("-", "").replace(" ", "").isalnum() else ""
    return Markup(
        f'<svg{attr} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.800" '
        f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{body}</svg>'
    )
