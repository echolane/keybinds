"""Examples for keybinds presets.

Run:
    python examples_presets.py

Manual test: press keys and click mouse, watch console output.
"""

import time

from keybinds.bind import Hook
from keybinds.types import SuppressPolicy
from keybinds.presets import (
    press, release, chord_released, click, hold, repeat, double_tap, sequence,
    mouse_press, mouse_release, mouse_hold, mouse_repeat, mouse_double_tap,
    with_,
)

hook = Hook()

def hit(name: str) -> None:
    print(f"[HIT] {name}", flush=True)

# Keyboard
hook.bind("ctrl+e", lambda: hit("ctrl+e press"), config=press())

hook.bind(
    "ctrl+r",
    lambda: hit("ctrl+r press (suppressed)"),
    config=press(suppress=SuppressPolicy.WHEN_MATCHED),
)

hook.bind("ctrl+t", lambda: hit("ctrl+t ON_RELEASE"), config=release())
hook.bind("ctrl+g", lambda: hit("ctrl+g ON_CHORD_RELEASED"), config=chord_released())

# Tap vs hold on same key
hook.bind("k", lambda: hit("k tap"), config=click(220))
hook.bind("k", lambda: hit("k hold"), config=hold(450))

# Repeat while held
hook.bind("j", lambda: hit("j repeat tick"), config=repeat(delay_ms=250, interval_ms=120))

# Double tap
hook.bind("d", lambda: hit("d double tap"), config=double_tap(300))

# Sequence
hook.bind("g,k,i", lambda: hit("sequence g,k,i"), config=sequence(600))

# “Partial override”: tweak a preset
FAST_REPEAT_SUPPRESSED = with_(
    repeat(delay_ms=180, interval_ms=60),
    suppress=SuppressPolicy.WHILE_ACTIVE,
)
hook.bind("space", lambda: hit("space fast repeat (while-active suppressed)"), config=FAST_REPEAT_SUPPRESSED)

# Mouse
hook.bind_mouse("left", lambda: hit("mouse left press"), config=mouse_press())
hook.bind_mouse("right", lambda: hit("mouse right hold"), config=mouse_hold(350))
hook.bind_mouse("left", lambda: hit("mouse left repeat tick"), config=mouse_repeat(delay_ms=180, interval_ms=80))
hook.bind_mouse("left", lambda: hit("mouse left double"), config=mouse_double_tap(300))

# Middle release suppression (requires paired suppression support for full click blocking)
hook.bind_mouse(
    "middle",
    lambda: hit("mouse middle release (suppressed)"),
    config=mouse_release(suppress=SuppressPolicy.WHEN_MATCHED),
)

print("Presets example running. Try:")
print("  KB: Ctrl+E, Ctrl+R, Ctrl+T, Ctrl+G, tap/hold K, hold J, double-tap D, sequence G,K,I, hold Space")
print("  Mouse: left click, hold right, hold left, double-click left, middle click (release)")
print("Ctrl+C to exit.")
while True:
    time.sleep(1)
