import threading
import time

from typing import Union, Optional, Callable, TypeVar, Generic, TYPE_CHECKING

from . import winput

from ._state import InputState
from ._window import get_window
from .types import Callback, FocusPolicy, BindConfig, MouseBindConfig
from .diagnostics import _NULL_BOUND_DIAGNOSTICS, build_bind_metadata, _BoundDiagnostics, _DiagnosticsManager, _DispatchTrace, _EventTrace

if TYPE_CHECKING:
    from ._hook import Hook


E = TypeVar("E", winput.KeyboardEvent, winput.MouseEvent)


class BaseBind(Generic[E]):
    def __init__(
        self,
        callback: Callback,
        *,
        config: Optional[Union[BindConfig, MouseBindConfig]] = None,
        hwnd: Optional[int] = None,
        dispatch: Optional[Callable[..., None]] = None,
        diagnostics: Optional[_DiagnosticsManager] = None,
    ) -> None:
        self.callback = callback
        self.config = config or BindConfig()
        self.window = get_window(hwnd)
        self._dispatch = dispatch or self._dispatch_inline
        self._diag_manager = diagnostics
        self._diag: _BoundDiagnostics = _NULL_BOUND_DIAGNOSTICS

        self._hold_token: int = 0

        self._focus_cache: bool = True
        self._focus_last_check_ms: int = 0
        self._focus_last_value: Optional[bool] = None

        self._last_fire_ms: int = 0
        self._fires: int = 0

        self._lock = threading.RLock()
        self.hook: Optional["Hook"] = None

    @staticmethod
    def _dispatch_inline(fn: Callback, trace: Optional[_DispatchTrace] = None) -> None:
        del trace
        fn()

    def _set_diagnostics_identity(self, bind_name: str, device: str) -> None:
        if self._diag_manager is None:
            self._diag = _NULL_BOUND_DIAGNOSTICS
            return
        try:
            metadata = build_bind_metadata(bind_name, device, self.config)
            self._diag = self._diag_manager.bind(bind_name, device, metadata=metadata)
        except Exception:
            self._diag = _NULL_BOUND_DIAGNOSTICS

    def _trace(self, event: E) -> "_EventTrace":
        return self._diag.start(event)

    def _check_name(self, pred) -> str:
        name = getattr(pred, "name", None)
        if isinstance(name, str) and name:
            return name
        name = getattr(pred, "__name__", None)
        if isinstance(name, str) and name and name != "<lambda>":
            return name
        return pred.__class__.__name__

    def _on_blur(self, trace: Optional[_EventTrace] = None) -> None:
        pol = self.config.focus
        if pol == FocusPolicy.CANCEL_ON_BLUR:
            if trace is not None:
                trace.note("state", "focus_blur_cancelled")
            self.reset()
        elif pol == FocusPolicy.PAUSE_ON_BLUR:
            if trace is not None:
                trace.note("state", "focus_blur_paused")
            self._hold_token += 1

    def _on_focus(self, trace: Optional[_EventTrace] = None) -> None:
        if trace is not None:
            trace.note("state", "focus_restored")

    def reset(self) -> None:
        pass

    def _window_ok(self, *, force: bool = False, trace: Optional[_EventTrace] = None) -> bool:
        if self.window is None:
            return True

        now_ms = int(time.monotonic() * 1000)
        cache_ms = self.config.timing.window_focus_cache_ms

        if (not force) and (now_ms - self._focus_last_check_ms) < cache_ms:
            if not self._focus_cache and trace is not None:
                trace.skip("window_mismatch", cached=True)
            return self._focus_cache

        self._focus_last_check_ms = now_ms
        try:
            focused = bool(self.window.is_focused())
        except Exception:
            focused = False

        if self._focus_last_value is None:
            self._focus_last_value = focused
        elif focused != self._focus_last_value:
            self._focus_last_value = focused
            if focused:
                self._on_focus(trace=trace)
            else:
                self._on_blur(trace=trace)

        self._focus_cache = focused
        if not focused and trace is not None:
            trace.skip("window_mismatch", cached=False)
        return focused

    def _checks_ok(self, event: E, state: InputState, trace: Optional[_EventTrace] = None) -> bool:
        for pred in self.config.checks:
            name = self._check_name(pred)
            try:
                passed = bool(pred(event, state))
            except Exception as exc:
                if trace is not None:
                    trace.skip(
                        "check_raised",
                        check=name,
                        error_type=type(exc).__name__,
                        error=str(exc),
                    )
                return False
            if not passed:
                if trace is not None:
                    trace.skip("check_failed", check=name)
                return False
            if trace is not None:
                trace.note("decision", "check_passed", check=name)
        return True

    def _cooldown_ok(self, now_ms: int, trace: Optional[_EventTrace] = None) -> bool:
        cd = self.config.timing.cooldown_ms
        ok = cd <= 0 or (now_ms - self._last_fire_ms) >= cd
        if (not ok) and trace is not None:
            trace.skip("cooldown_active", cooldown_ms=cd, since_last_ms=(now_ms - self._last_fire_ms))
        return ok

    def _max_fires_ok(self, trace: Optional[_EventTrace] = None) -> bool:
        mx = self.config.constraints.max_fires
        ok = mx is None or self._fires < mx
        if (not ok) and trace is not None:
            trace.skip("max_fires_reached", max_fires=mx, fires=self._fires)
        return ok

    def can_fire_now(self, ts_ms: int, trace: Optional[_EventTrace] = None) -> bool:
        if not self._cooldown_ok(ts_ms, trace=trace):
            return False
        if not self._max_fires_ok(trace=trace):
            return False
        return True

    def _fire(self, trace: Optional[_DispatchTrace] = None) -> None:
        self._dispatch(self.callback, trace)
