# keybinds

Flexible global keyboard & mouse hotkeys for Windows.

![Python](https://img.shields.io/badge/python-3.7%2B-blue)
![Platform](https://img.shields.io/badge/platform-windows-lightgrey)
![License](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-active-success)
![PyPI](https://img.shields.io/pypi/v/keybinds)

**keybinds** is a Python library for global keyboard and mouse binds on Windows, with support for hotkeys, logical key binds, text matching, and text abbreviations.

It supports:
- global keyboard binds: single keys, chords (`ctrl+e`), and sequences (`g,k,i`)
- global mouse binds: `left`, `right`, `middle`, `x1`, `x2`
- rich triggers: press, release, click, hold, repeat, double tap, and sequence
- suppression and injected-input policies
- sync and async callbacks
- decorator helpers and a simple API
- experimental logical binds, typed-text matching, and text abbreviations
- unified unbind helpers for bind handles, decorated functions, and bind collections

Powered by a bundled/modified **[winput](https://github.com/Zuzu-Typ/winput)** for reliable input suppression and precise control.

---

## Installation

```bash
pip install keybinds
```

### Requirements

- Windows
- Python 3.7+
- `typing_extensions` on Python 3.7

---

## Quick Start

```python
from keybinds import Hook

hook = Hook()
hook.bind("ctrl+e", lambda: print("Inventory"))
hook.bind_mouse("left", lambda: print("Fire"))

hook.join()
```

---

## Decorator Style

Stable decorator helpers:

```python
import keybinds
from keybinds.decorators import bind_key, bind_mouse

@bind_key("ctrl+e")
def inventory():
    print("Inventory")

@bind_mouse("left")
def fire():
    print("Bang")

keybinds.join()
```

Decorators use the default hook automatically.

### Experimental logical/text decorators

```python
import keybinds
from keybinds.decorators import bind_logical, bind_text, bind_abbreviation

# Experimental API: may change in future releases.

@bind_logical("ctrl+A")
def logical_inventory():
    print("Logical inventory")

@bind_text("hello")
def saw_hello():
    print("Hello typed")

@bind_abbreviation("brb", "be right back")
def expanded_brb():
    print("Expanded brb")

keybinds.join()
```

For non-decorator usage, `keybinds.add_abbreviation(...)` is also available.

---

## When to use what

- `bind(...)` — regular keyboard shortcuts based on key expressions
- `bind_mouse(...)` — mouse button binds
- `bind_logical(...)` — experimental layout-aware logical key binds
- `bind_text(...)` — experimental typed-text matching
- `add_abbreviation(...)` / `bind_abbreviation(...)` — experimental text expansion

For normal shortcuts, prefer `bind(...)`. For typed text, prefer `bind_text(...)` instead of text-like expressions passed to `bind_logical(...)`.

---

## Unbinding

Bind methods return bind handles directly:

```python
b = hook.bind("ctrl+e", callback)
hook.unbind(b)
```

Decorators attach created bind handles to the function:

- `func.binds` always contains a list of all created bind objects
- `func.bind` is kept as a compatibility alias:
  - single bind → `func.bind` is that bind object
  - multiple binds → `func.bind` is a list of bind objects

You can unbind by handle, by function, or by a bind collection:

```python
hook.unbind(my_callback)
hook.unbind(my_callback.binds)
hook.unbind(my_callback.bind)

keybinds.unbind(my_callback)
```

Top-level helpers use the default hook. If you use multiple hooks, prefer `hook.unbind(...)` on the specific hook.

---

## Bind state and waiting

All bind objects expose two small runtime helpers:

```python
if bind.is_pressed():
    print("bind is currently active")

bind.wait()          # wait until the bind fires
bind.wait(0.5)       # wait up to 0.5s, returns True/False
```

`is_pressed()` checks whether the bind is currently pressed.
`wait(timeout=None)` blocks until the bind fires and returns `True`, or returns `False` on timeout.

---

## Keyboard Basics

### Press (default)

```python
hook.bind("ctrl+e", lambda: print("Pressed"))
```

### Release

```python
from keybinds.types import BindConfig, Trigger

hook.bind(
    "ctrl+t",
    lambda: print("Released"),
    config=BindConfig(trigger=Trigger.ON_RELEASE),
)
```

### Hold

```python
from keybinds.types import BindConfig, Trigger, Timing

hook.bind(
    "h",
    lambda: print("Held"),
    config=BindConfig(
        trigger=Trigger.ON_HOLD,
        timing=Timing(hold_ms=400),
    ),
)
```

### Repeat (auto-fire while held)

```python
from keybinds.types import BindConfig, Trigger, Timing

hook.bind(
    "space",
    lambda: print("Tick"),
    config=BindConfig(
        trigger=Trigger.ON_REPEAT,
        timing=Timing(hold_ms=200, repeat_interval_ms=80),
    ),
)
```

### Double tap

```python
from keybinds.types import BindConfig, Trigger

hook.bind(
    "g",
    lambda: print("Dash"),
    config=BindConfig(trigger=Trigger.ON_DOUBLE_TAP),
)
```

### Sequence

```python
from keybinds.types import BindConfig, Trigger

hook.bind(
    "g,k,i",
    lambda: print("Secret combo"),
    config=BindConfig(trigger=Trigger.ON_SEQUENCE),
)
```

---

## Mouse Basics

```python
from keybinds.types import MouseBindConfig, Trigger

hook.bind_mouse(
    "middle",
    lambda: print("Middle pressed"),
    config=MouseBindConfig(trigger=Trigger.ON_PRESS),
)
```

Mouse buttons:

- `left`
- `right`
- `middle`
- `x1`
- `x2`

---

## Suppression (block input from apps)

```python
from keybinds.types import BindConfig, SuppressPolicy

hook.bind(
    "ctrl+r",
    lambda: print("Reload"),
    config=BindConfig(suppress=SuppressPolicy.WHEN_MATCHED),
)
```

Policies:

- `NEVER`
- `WHEN_MATCHED`
- `WHILE_ACTIVE`
- `WHILE_EVALUATING`
- `ALWAYS`

---

## Injected (synthetic) input policy

Control how injected input (macros, `SendInput`, automation tools) is handled:

```python
from keybinds.types import BindConfig, InjectedPolicy

hook.bind(
    "f1",
    lambda: print("Only physical"),
    config=BindConfig(injected=InjectedPolicy.IGNORE),
)
```

Policies:

- `ALLOW`
- `IGNORE`
- `ONLY`

---

## Strict Chords

```python
from keybinds.types import BindConfig, Constraints, ChordPolicy

hook.bind(
    "ctrl+shift+u",
    lambda: print("Strict"),
    config=BindConfig(
        constraints=Constraints(chord_policy=ChordPolicy.STRICT)
    ),
)
```

---

## Checks / Predicates

```python
def not_injected(event, state):
    return not event.injected

hook.bind("f1", lambda: print("Checked"), checks=not_injected)
```

You can also pass:

- a single callable
- a list/tuple of callables
- `Checks(...)`

---

## Async Callbacks

Callbacks may be `async def`. If a callback returns an awaitable, **keybinds** schedules it on an asyncio loop.

```python
import asyncio
from keybinds import Hook
from keybinds.decorators import bind_key

hook = Hook()

@bind_key("f1", hook=hook)
async def ping():
    await asyncio.sleep(0.1)
    print("async ok")

hook.join()
```

If your app already runs its own event loop, pass it via `Hook(asyncio_loop=...)` and avoid calling blocking `join()` on that thread.

---

## Presets (shortcut configs)

```python
from keybinds.presets import press, release, click, hold, repeat, double_tap, sequence

hook.bind("ctrl+e", lambda: print("press"),   config=press())
hook.bind("ctrl+e", lambda: print("release"), config=release())
hook.bind("k",      lambda: print("tap"),     config=click(220))
hook.bind("k",      lambda: print("hold"),    config=hold(450))
hook.bind("space",  lambda: print("tick"),    config=repeat(delay_ms=200, interval_ms=80))
hook.bind("d",      lambda: print("dash"),    config=double_tap(window_ms=250))
hook.bind("g,k,i",  lambda: print("combo"),   config=sequence(timeout_ms=600))
```

---

## Simple API

For common cases, use the lightweight decorator wrapper:

```python
from keybinds.simple import hotkey, mouse, run

@hotkey("ctrl+e")
def inventory():
    print("Inventory")

@hotkey("space", repeat=80, delay=200)
def autofire():
    print("Bang")

@hotkey("f", hold=400)
def charge():
    print("Charged")

@mouse("left")
def on_left():
    print("Mouse pressed")

run()
```

Supports common patterns with simple flags:

- `release=True`
- `hold=400`
- `repeat=80` (optionally `delay=200`)
- `sequence=True` (optionally `timeout=600`)
- `double_tap=True`
- `suppress=True`

---

## Documentation

- **[Advanced Usage.md](./Advanced%20Usage.md)** — advanced triggers, constraints, suppression, callbacks, and API details
- **[Diagnostics.md](./Diagnostics.md)** — troubleshooting and runtime introspection
- **[Logical Binds and Abbreviations.md](./Logical%20Binds%20and%20Abbreviations.md)** — experimental logical binds, typed text, and abbreviations
- **[Developer Notes - Logical.md](./Developer%20Notes%20-%20Logical.md)** — developer-oriented notes on logical internals

---

## Notes

Logical binds, typed-text matching, and abbreviations are currently **experimental**. The API and behavior may still change in future releases.

## Suppression limitations

On Windows, suppression depends on low-level hook order. See [Advanced Usage — Hook chain limitations and `reinstall_hooks()`](Advanced%20Usage.md#41-hook-chain-limitations-and-reinstall_hooks).

## License

MIT License

## Third-party Components

This project bundles a modified copy of [winput](https://github.com/Zuzu-Typ/winput) (originally by Zuzu_Typ, zlib/libpng license), extended so `keybinds` can detect injected keyboard and mouse hook events.
The original license text is included in `keybinds/winput/LICENSE`.

## Contributing

PRs and issues are welcome:

- bug fixes
- performance improvements
- new triggers
- documentation
- examples

## ⭐ If you like it

Star the repo — it helps a lot.
