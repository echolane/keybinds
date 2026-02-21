
# keybinds

Flexible and high-performance global keyboard & mouse hotkeys for Windows.

![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![Platform](https://img.shields.io/badge/platform-windows-lightgrey)
![License](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-active-success)
![PyPI](https://img.shields.io/pypi/v/keybinds)

**keybinds** is a Python library for building fully customizable global keybinds and mouse binds using low-level Windows hooks.

It supports:
- keyboard **single keys**, **chords** (`ctrl+e`), **sequences** (`g,k,i`)
- mouse button binds (`left`, `right`, `middle`, `x1`, `x2`)
- rich triggers (press / release / click / hold / repeat / double tap / sequence)
- suppression and injected-input policies
- sync + async callbacks
- decorators and config-driven API

Powered by a bundled/modified **[winput](https://github.com/Zuzu-Typ/winput)** for reliable input suppression and precise control.

---

## Installation

```bash
pip install keybinds
````

### Requirements

* Windows
* Python 3.9+

---

## Comparison (Windows hotkeys)

| Feature | keybinds | keyboard | pynput | AutoHotkey |
|---|---:|---:|---:|---:|
| Cross-platform | ❌ (Windows only) | ⚠️ Windows/Linux (+ experimental macOS) | ✅ | ❌ (Windows only) |
| Python-native library | ✅ | ✅ | ✅ | ❌ (separate DSL/tool) |
| Global keyboard hooks | ✅ | ✅ | ✅ | ✅ |
| Chords / combos | ✅ | ✅ | ✅* | ✅ |
| Sequences | ✅ | ✅ | ❌ | ✅ |
| Window-scoped/context hotkeys | ✅ (`hwnd`) | ❌ | ❌ | ✅ |
| Async callbacks (`asyncio`) | ✅ | ❌ | ❌ | ❌ |
| Built-in trigger model (hold/repeat/double-tap/sequence/chord lifecycle) | ✅ | ⚠️ partial | ❌ | ⚠️ script-level patterns |
| Fine-grained constraints (strict chords, order policy, injected policy) | ✅ | ❌ | ❌ | ⚠️ possible, but not as a Python API model |

\* `pynput` provides `HotKey` / `GlobalHotKeys` for combinations, but not built-in sequence-style hotkeys.

---

## Quick Start

```python
from keybinds.bind import Hook

hook = Hook()
hook.bind("ctrl+e", lambda: print("Inventory"))
hook.bind_mouse("left", lambda: print("Fire"))

hook.join()
```

---

## Decorator Style (no manual Hook required)

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

Decorators use a default hook automatically.

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

* `left`
* `right`
* `middle`
* `x1`
* `x2`

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

* `NEVER`
* `WHEN_MATCHED`
* `WHILE_ACTIVE`
* `WHILE_EVALUATING`
* `ALWAYS`

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

* `ALLOW`
* `IGNORE`
* `ONLY`

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
from keybinds.types import BindConfig, Checks

def not_injected(event, state):
    return not event.injected

hook.bind(
    "f1",
    lambda: print("Checked"),
    config=BindConfig(checks=Checks([not_injected])),
)
```

You can also pass:

* a single callable
* a list/tuple of callables
* `Checks(...)`

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

More presets, profiles and composition patterns are in **[Advanced Usage.md](./Advanced%20Usage.md)**.

---

## Simple API

For common cases, use the lightweight decorator wrapper:

```python
from keybinds.simple import hotkey, run

@hotkey("ctrl+e")
def inventory():
    print("Inventory")

@hotkey("space", repeat=80, delay=200)
def autofire():
    print("Bang")

@hotkey("f", hold=400)
def charge():
    print("Charged")

run()
```

Supports common patterns with simple flags:

* `release=True`
* `hold=400`
* `repeat=80` (optionally `delay=200`)
* `sequence=True` (optionally `timeout=600`)
* `double_tap=True`
* `suppress=True`

---

## Performance

Measured using `examples/benchmark.py`:

- p50 ≈ 0.21 ms  
- p99 ≈ 0.35 ms  
- max < 0.7 ms (rare spikes up to 3–5 ms)

Latency includes hook dispatch and callback scheduling (no heavy user code).

## License

MIT License

## Third-party Components

This project bundles a modified copy of [winput](https://github.com/Zuzu-Typ/winput) (originally by Zuzu_Typ, zlib/libpng license).
The original license text is included in `keybinds/winput/LICENSE`.

## Contributing

PRs and issues are welcome:

* bug fixes
* performance improvements
* new triggers
* documentation
* examples

## ⭐ If you like it

Star the repo — it helps a lot.
