import keybinds
from keybinds.types import BindConfig, MouseBindConfig, SuppressPolicy, Trigger, Timing

print("=== keybinds suppression manual test ===")
print("Esc  -> exit")
print("F1   -> reinstall hooks")
print()
print("Keyboard:")
print("  F               -> ON_PRESS + WHEN_MATCHED")
print("  G (double tap)  -> ON_DOUBLE_TAP + WHEN_MATCHED")
print("  Ctrl+R          -> ON_RELEASE + WHEN_MATCHED")
print("  Ctrl+Shift+X    -> ON_CHORD_RELEASED + WHEN_MATCHED")
print("  J,K             -> ON_SEQUENCE + WHEN_MATCHED")
print()
print("Mouse:")
print("  X1              -> ON_PRESS + WHEN_MATCHED")
print("  X2              -> ON_RELEASE + WHEN_MATCHED")
print("  Middle double   -> ON_DOUBLE_TAP + WHEN_MATCHED")
print("  Right click     -> ON_CLICK + WHEN_MATCHED (should NOT suppress)")
print()
print("Tip: run another listener in parallel, e.g. `keyboard.read_key()` or any mouse test app.")
print("Use F1 after starting that listener to test `reinstall_hooks()` ordering.")
print()


# ----------------------------
# Utility / control
# ----------------------------

@keybinds.bind_key("esc")
def quit_app():
    print("[SYS] exit")
    raise SystemExit


@keybinds.bind_key("f1")
def reinstall():
    print("[SYS] reinstall_hooks()")
    keybinds.reinstall_hooks()


# ----------------------------
# Keyboard suppression tests
# ----------------------------

@keybinds.bind_key(
    "f",
    config=BindConfig(
        trigger=Trigger.ON_PRESS,
        suppress=SuppressPolicy.WHEN_MATCHED,
    ),
)
def kb_press():
    print("[KB] F -> ON_PRESS fired")
    print("     expected: apps/listeners should NOT see F down, repeats, or up")


@keybinds.bind_key(
    "g",
    config=BindConfig(
        trigger=Trigger.ON_DOUBLE_TAP,
        suppress=SuppressPolicy.WHEN_MATCHED,
        timing=Timing(double_tap_window_ms=300),
    ),
)
def kb_double_tap():
    print("[KB] G -> ON_DOUBLE_TAP fired")
    print("     expected: first tap passes, second tap down/up is suppressed")


@keybinds.bind_key(
    "ctrl+r",
    config=BindConfig(
        trigger=Trigger.ON_RELEASE,
        suppress=SuppressPolicy.WHEN_MATCHED,
    ),
)
def kb_release():
    print("[KB] Ctrl+R -> ON_RELEASE fired")
    print("     expected: completing key down/up is suppressed")


@keybinds.bind_key(
    "ctrl+shift+x",
    config=BindConfig(
        trigger=Trigger.ON_CHORD_RELEASED,
        suppress=SuppressPolicy.WHEN_MATCHED,
    ),
)
def kb_chord_released():
    print("[KB] Ctrl+Shift+X -> ON_CHORD_RELEASED fired")
    print("     expected: only the last pressed key (that completed the chord) down/up is suppressed")


@keybinds.bind_key(
    "j,k",
    config=BindConfig(
        trigger=Trigger.ON_SEQUENCE,
        suppress=SuppressPolicy.WHEN_MATCHED,
    ),
)
def kb_sequence():
    print("[KB] J,K -> ON_SEQUENCE fired")
    print("     expected: final sequence key down/up is suppressed")


# ----------------------------
# Mouse suppression tests
# ----------------------------

@keybinds.bind_mouse(
    "x1",
    config=MouseBindConfig(
        trigger=Trigger.ON_PRESS,
        suppress=SuppressPolicy.WHEN_MATCHED,
    ),
)
def mouse_press():
    print("[MS] X1 -> ON_PRESS fired")
    print("     expected: mouse down/up suppressed")


@keybinds.bind_mouse(
    "x2",
    config=MouseBindConfig(
        trigger=Trigger.ON_RELEASE,
        suppress=SuppressPolicy.WHEN_MATCHED,
    ),
)
def mouse_release():
    print("[MS] X2 -> ON_RELEASE fired")
    print("     expected: mouse down/up suppressed")


@keybinds.bind_mouse(
    "middle",
    config=MouseBindConfig(
        trigger=Trigger.ON_DOUBLE_TAP,
        suppress=SuppressPolicy.WHEN_MATCHED,
        timing=Timing(double_tap_window_ms=300),
    ),
)
def mouse_double():
    print("[MS] Middle -> ON_DOUBLE_TAP fired")
    print("     expected: first tap passes, second tap down/up is suppressed")


@keybinds.bind_mouse(
    "right",
    config=MouseBindConfig(
        trigger=Trigger.ON_CLICK,
        suppress=SuppressPolicy.WHEN_MATCHED,
        timing=Timing(hold_ms=220),
    ),
)
def mouse_click():
    print("[MS] Right -> ON_CLICK fired")
    print("     expected: callback fires, BUT click itself is NOT suppressed")


keybinds.join()
