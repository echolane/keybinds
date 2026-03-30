import time
from keybinds import Hook

hook = Hook()

kb = hook.bind("ctrl+e", lambda: print("kb fired"))
ms = hook.bind_mouse("left", lambda: print("mouse fired"))
lg = hook.bind_logical("ctrl+A", lambda: print("logical fired"))
tx = hook.bind_text("hello", lambda: print("text fired"))
ab = hook.add_abbreviation("brb", "be right back")

items = {
    "keyboard": kb,
    "mouse": ms,
    "logical": lg,
    "text": tx,
    "abbreviation": ab,
}

hook.start()

try:
    while True:
        print({name: b.is_pressed() for name, b in items.items()})
        time.sleep(0.2)
except KeyboardInterrupt:
    hook.close()
