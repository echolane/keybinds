import keybinds
from keybinds.decorators import bind_key, bind_logical, bind_text, add_abbreviation, bind_abbreviation, bind_mouse
from keybinds.types import BindConfig, Trigger, Timing, SuppressPolicy, MouseBindConfig, LogicalConfig


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


# @bind_logical("ctrl+A")
def logical_inventory():
    print("logical inventory")


# @bind_text("hello", logical_config=LogicalConfig(case_sensitive=False))
def hello_text():
    print("typed hello")


# @bind_abbreviation("brb", "be right back")
def brb_expanded():
    print("expanded brb")


print("Running manual test.")
print("CTRL + E: inventory")
print("K: hold k (450ms)")
print("CTRL + R: reload (suppressed)")
print("MIDDLE: middle mouse suppressed")

print()
print("Logical binds (UNCOMMENT TO TEST):")
print("CTRL + A (logical): logical inventory")
print("Type hello: typed hello")
print("Type brb: expansion + callback")
print()

print("Ctrl+C to exit.")
keybinds.join()
