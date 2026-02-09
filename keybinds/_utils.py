from __future__ import annotations
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from wincontrol import Window



def get_window(hwnd: Optional[int]) -> Optional[Window]:
    if hwnd is None:
        return None

    try:
        from wincontrol import Window
    except Exception:  # pragma: no cover
        Window = None  # type: ignore

    return Window(hwnd) if Window is not None else None
