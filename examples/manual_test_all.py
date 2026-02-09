# Manual, practical test suite for keyboard+mouse.
# Run: python examples/manual_test_all.py

from keybinds.bind import Hook
from keybinds.types import (
    BindConfig, MouseBindConfig, Trigger, SuppressPolicy, Timing,
    Constraints, ChordPolicy
)

hook = Hook()

def hit(name: str):
    print(f"[HIT] {name}", flush=True)

# Keyboard
hook.bind("ctrl+e", lambda: hit("KB ctrl+e press"))
hook.bind("ctrl+t", lambda: hit("KB ctrl+t release"), config=BindConfig(trigger=Trigger.ON_RELEASE))

hook.bind("k", lambda: hit("KB k click"), config=BindConfig(trigger=Trigger.ON_CLICK, timing=Timing(hold_ms=220)))
hook.bind("k", lambda: hit("KB k hold"),  config=BindConfig(trigger=Trigger.ON_HOLD,  timing=Timing(hold_ms=450)))

hook.bind("j", lambda: hit("KB j repeat"), config=BindConfig(trigger=Trigger.ON_REPEAT, timing=Timing(hold_ms=250, repeat_interval_ms=120)))

hook.bind("g", lambda: hit("KB g double"), config=BindConfig(trigger=Trigger.ON_DOUBLE_TAP, timing=Timing(double_tap_window_ms=300)))

hook.bind("g,k,i", lambda: hit("KB seq g,k,i"), config=BindConfig(trigger=Trigger.ON_SEQUENCE, timing=Timing(chord_timeout_ms=550)))

hook.bind(
    "ctrl+shift+u",
    lambda: hit("KB strict ctrl+shift+u"),
    config=BindConfig(trigger=Trigger.ON_PRESS, constraints=Constraints(chord_policy=ChordPolicy.STRICT)),
)

hook.bind(
    "ctrl+r",
    lambda: hit("KB ctrl+r suppressed"),
    config=BindConfig(trigger=Trigger.ON_PRESS, suppress=SuppressPolicy.WHEN_MATCHED),
)

# Mouse
hook.bind_mouse("left", lambda: hit("MOUSE left press"), config=MouseBindConfig(trigger=Trigger.ON_PRESS))
hook.bind_mouse("right", lambda: hit("MOUSE right hold"), config=MouseBindConfig(trigger=Trigger.ON_HOLD, timing=Timing(hold_ms=350)))
hook.bind_mouse("left", lambda: hit("MOUSE left repeat"), config=MouseBindConfig(trigger=Trigger.ON_REPEAT, timing=Timing(hold_ms=180, repeat_interval_ms=80)))
hook.bind_mouse("left", lambda: hit("MOUSE left double"), config=MouseBindConfig(trigger=Trigger.ON_DOUBLE_TAP, timing=Timing(double_tap_window_ms=300)))

# Middle suppress
hook.bind_mouse(
    "middle",
    lambda: hit("MOUSE middle press suppressed"),
    config=MouseBindConfig(trigger=Trigger.ON_PRESS, suppress=SuppressPolicy.WHEN_MATCHED),
)

hook.bind_mouse(
    "middle",
    lambda: hit("MOUSE middle release suppressed"),
    config=MouseBindConfig(trigger=Trigger.ON_RELEASE, suppress=SuppressPolicy.WHEN_MATCHED),
)

print("Running manual test. Press keys / click mouse. Ctrl+C to exit.")
hook.join()
