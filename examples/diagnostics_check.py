from keybinds.bind import Hook
from keybinds.types import BindConfig, Trigger, Timing
from keybinds.diagnostics import DiagnosticsConfig


hook = Hook(
    diagnostics=DiagnosticsConfig(
        enabled=True,
        level="decisions",
        ring_size=3000,
    )
)


def hit(name: str):
    print(f"[HIT] {name}", flush=True)


hook.bind("ctrl+e", lambda: hit("ctrl+e"))
hook.bind("k", lambda: hit("k click"), config=BindConfig(trigger=Trigger.ON_CLICK, timing=Timing(hold_ms=220)))
hook.bind("k", lambda: hit("k hold"), config=BindConfig(trigger=Trigger.ON_HOLD, timing=Timing(hold_ms=450)))
hook.bind("j", lambda: hit("j repeat"), config=BindConfig(trigger=Trigger.ON_REPEAT, timing=Timing(hold_ms=250, repeat_interval_ms=120)))
hook.bind("g,k,i", lambda: hit("sequence g,k,i"), config=BindConfig(trigger=Trigger.ON_SEQUENCE, timing=Timing(chord_timeout_ms=550)))

print("1) Press Ctrl+E, then Enter here.")
input()
print(hook.explain("ctrl+e", last_ms=5000).render_text())

print("\n2) Tap K shortly, then Enter here.")
input()
print(hook.explain("k", last_ms=5000).render_text())

print("\n3) Hold K longer, then Enter here.")
input()
print(hook.explain("k", last_ms=5000).render_text())

print("\n4) Hold J for repeat, then Enter here.")
input()
print(hook.explain("j", last_ms=7000).render_text())

print("\n5) Press G, K, I, then Enter here.")
input()
print(hook.explain("g,k,i", last_ms=7000).render_text())

hook.stop()
