import keybinds
from keybinds.decorators import bind_key, bind_mouse
from keybinds.types import BindConfig, Trigger, Timing, SuppressPolicy, MouseBindConfig

@bind_key("ctrl+e")
def inventory():
    print("inventory")

@bind_key("k", config=BindConfig(trigger=Trigger.ON_HOLD, timing=Timing(hold_ms=450)))
def hold_k():
    print("hold k")

@bind_key("ctrl+r", config=BindConfig(trigger=Trigger.ON_PRESS, suppress=SuppressPolicy.WHEN_MATCHED))
def reload():
    print("reload (suppressed)")

@bind_mouse("middle", config=MouseBindConfig(trigger=Trigger.ON_PRESS, suppress=SuppressPolicy.WHEN_MATCHED))
def middle():
    print("middle suppressed")

print("Running manual test.")
print("CTRL + E: inventory")
print("K: hold k (450ms)")
print("CTRL + R: reload (suppressed)")
print("MIDDLE: middle mouse suppressed")
print("Ctrl+C to exit.")
keybinds.join()
