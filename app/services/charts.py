"""Gelir-gider sütun grafiğinin ölçüleri. SVG şablonda çizilir; burada yalnızca geometri hesaplanır."""
from __future__ import annotations

from dataclasses import dataclass

from .reports import nice_ceiling


@dataclass
class Column:
    label: str          # eksen yazısı
    title: str          # ipucu başlığı
    income: int
    expense: int
    current: bool = False

    @property
    def net(self) -> int:
        return self.income - self.expense


def _bar_path(x: float, y: float, w: float, h: float, r: float = 4) -> str:
    """Üstü yuvarlak, tabanı düz sütun."""
    if h <= 0:
        return ""
    r = min(r, h, w / 2)
    return (
        f"M{x:.1f},{y + h:.1f} V{y + r:.1f} Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f} "
        f"H{x + w - r:.1f} Q{x + w:.1f},{y:.1f} {x + w:.1f},{y + r:.1f} V{y + h:.1f} Z"
    )


def column_chart(
    columns: list[Column], *, width: int = 720, height: int = 250, bar: float = 15, gap: float = 2
) -> dict:
    """İki serili (gelir, gider) gruplanmış sütun grafiği.

    Tek eksen, sıfırdan başlar; sütunlar en çok `bar` kalınlığında, aralarında `gap` boşluk.
    """
    pad_l, pad_r, pad_t, pad_b = 58, 8, 14, 30
    top = nice_ceiling(max([c.income for c in columns] + [c.expense for c in columns] + [0]))
    plot_w, plot_h = width - pad_l - pad_r, height - pad_t - pad_b
    band = plot_w / max(len(columns), 1)
    bar = min(bar, max((band - gap - 8) / 2, 3))
    base = pad_t + plot_h

    def y_of(value: int) -> float:
        return base - (value / top) * plot_h

    groups = []
    for i, col in enumerate(columns):
        cx = pad_l + band * i + band / 2
        groups.append({
            "col": col,
            "cx": round(cx, 1),
            "band_x": round(pad_l + band * i, 1),
            "band_w": round(band, 1),
            "income_path": _bar_path(cx - gap / 2 - bar, y_of(col.income), bar, base - y_of(col.income)),
            "expense_path": _bar_path(cx + gap / 2, y_of(col.expense), bar, base - y_of(col.expense)),
        })
    ticks = [{"y": round(y_of(top * k // 4), 1), "value": top * k // 4} for k in range(5)]
    return {
        "w": width, "h": height, "base": base, "pad_l": pad_l, "pad_r": pad_r, "pad_t": pad_t,
        "plot_h": plot_h, "groups": groups, "ticks": ticks,
        "empty": all(c.income == 0 and c.expense == 0 for c in columns),
    }
