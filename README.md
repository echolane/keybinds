# keybinds

> Flexible and high-performance keyboard & mouse hotkeys for Windows.

![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![Platform](https://img.shields.io/badge/platform-windows-lightgrey)
![License](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-active-success)
![PyPI](https://img.shields.io/pypi/v/keybinds)

**keybinds** is a Python library for building fully customizable global keybinds and mouse binds using low-level Windows hooks.

It supports chords (`ctrl+e`), sequences (`g,k,i`), rich triggers (press / release / hold / repeat / double tap), strict constraints, suppress/injected policies, and user-defined checks — while keeping the API clean and configuration-driven.

Lightweight. Powered by **[winput](https://github.com/Zuzu-Typ/winput)** for reliable input suppression and precise control.

---

## ✨ Features

### Keyboard
- Single keys: `k`, `f1`, `space`
- Chords: `ctrl+e`, `ctrl+shift+x`
- Sequences: `g,k,i`

### Mouse
- Buttons: `left`, `right`, `middle`, `x1`, `x2`

### Triggers
- `ON_PRESS`
- `ON_RELEASE`
- `ON_CLICK`
- `ON_HOLD`
- `ON_REPEAT`
- `ON_DOUBLE_TAP`
- `ON_SEQUENCE`
- `ON_CHORD_RELEASED`

### Advanced
- Input **suppression** (block events from reaching apps)
- **Injected policy**: control whether synthetic (e.g. macro) events are handled or ignored.
- **Strict chords**
- **Timing controls** (hold/delay/intervals/windows)
- **Predicates / checks**
- Clean **Config + Enum** design
- Decorator support
- Very fast hook path (callbacks run outside hook thread)

**Performance (examples/benchmark.py):** p50 ~0.21 ms, p99 ~0.35 ms, max <0.7ms (rarely 3–5 ms).

---

## 🚀 Installation

### From [PyPI](https://pypi.org/project/keybinds)

```bash
pip install keybinds
```

### Requirements

- Windows
- Python 3.9+
- `winput` (bundled)

---

## ⚡ Quick Start

```python
import time
from keybinds.bind import Hook

hook = Hook()

hook.bind("ctrl+e", lambda: print("Inventory"))
hook.bind_mouse("left", lambda: print("Fire"))

hook.join()
```

---

## 📦 Examples

Run any example directly:

```bash
python examples/quickstart.py
python examples/decorators.py
python examples/examples_presets.py
python examples/manual_test_all.py
```


# Usage

## Keyboard

### Simple press

```python
hook.bind("ctrl+e", lambda: print("Pressed"))
```

---

### Release

```python
from keybinds.types import BindConfig, Trigger

hook.bind(
    "ctrl+t",
    lambda: print("Released"),
    config=BindConfig(trigger=Trigger.ON_RELEASE)
)
```

---

### Hold

```python
from keybinds.types import BindConfig, Trigger, Timing

hook.bind(
    "h",
    lambda: print("Held"),
    config=BindConfig(
        trigger=Trigger.ON_HOLD,
        timing=Timing(hold_ms=400)
    )
)
```

---

### Repeat (auto-fire)

```python
hook.bind(
    "space",
    lambda: print("Tick"),
    config=BindConfig(
        trigger=Trigger.ON_REPEAT,
        timing=Timing(hold_ms=200, repeat_interval_ms=80)
    )
)
```

---

### Double tap

```python
hook.bind(
    "g",
    lambda: print("Dash"),
    config=BindConfig(
        trigger=Trigger.ON_DOUBLE_TAP
    )
)
```

---

### Sequence

```python
hook.bind(
    "g,k,i",
    lambda: print("Secret combo"),
    config=BindConfig(trigger=Trigger.ON_SEQUENCE)
)
```

---

## Mouse

```python
from keybinds.types import MouseBindConfig, Trigger

hook.bind_mouse(
    "middle",
    lambda: print("Middle pressed"),
    config=MouseBindConfig(trigger=Trigger.ON_PRESS)
)
```

---

## Suppress (block input)

Prevent the event from reaching applications:

```python
from keybinds.types import SuppressPolicy

hook.bind(
    "ctrl+r",
    lambda: print("Reload"),
    config=BindConfig(
        suppress=SuppressPolicy.WHEN_MATCHED
    )
)
```

Policies:

| Policy           | Behavior                          |
| ---------------- | --------------------------------- |
| NEVER            | never suppress                    |
| WHEN_MATCHED     | suppress only when callback fires |
| WHILE_ACTIVE     | suppress while chord active       |
| WHILE_EVALUATING | suppress while matching           |
| ALWAYS           | always suppress                   |

---

## Injected (synthetic) events

Control how synthetic / injected input (macros, SendInput, other tools) is handled:

```python
from keybinds.types import InjectedPolicy

hook.bind(
    "f1",
    callback,
    config=BindConfig(injected=InjectedPolicy.IGNORE)
)
```

| Policy | Behavior                                |
| ------ | --------------------------------------- |
| ALLOW  | handle both physical and injected input |
| IGNORE | ignore injected completely              |
| ONLY   | react only to injected events           |

---

## Strict chord

Require exact keys only:

```python
from keybinds.types import Constraints, ChordPolicy

hook.bind(
    "ctrl+shift+u",
    lambda: print("Strict"),
    config=BindConfig(
        constraints=Constraints(chord_policy=ChordPolicy.STRICT)
    )
)
```

---

## Checks / Predicates

Add additional conditions to a keybind:

```python
from keybinds.types import Checks

hook.bind(
    "f1",
    callback,
    config=keybinds.BindConfig(
        checks=lambda event, state: event.extra_info == 0xDEADBEEF
        # checks=[check1, check2]
        # checks=Checks([check1, check2])
    )
)
```

---

## Decorators

Cleaner syntax:

```python
from keybinds.decorators import bind_key, bind_mouse

@bind_key("ctrl+e")
def inventory():
    print("Inventory")

@bind_mouse("left")
def fire():
    print("Bang")
```

---

# Presets & Profiles

If you don't want to write `BindConfig(...)` / `MouseBindConfig(...)` everywhere, use presets:

```python
from keybinds.presets import press, release, click, hold, repeat, double_tap, sequence

hook.bind("ctrl+e", lambda: print("press"),   config=press())
hook.bind("ctrl+e", lambda: print("release"), config=release())

hook.bind("k", lambda: print("tap"),  config=click(220))
hook.bind("k", lambda: print("hold"), config=hold(450))

hook.bind("space", lambda: print("tick"), config=repeat(delay_ms=200, interval_ms=80))
hook.bind("d", lambda: print("dash"), config=double_tap(window_ms=250))
hook.bind("g,k,i", lambda: print("combo"), config=sequence(timeout_ms=600))
```

### Ready-to-use profiles (practical bundles)

Profiles bundle multiple configs for common patterns.

#### Tap vs Hold on the same key

```python
from keybinds.presets import tap_hold

th = tap_hold(tap_ms=220, hold_ms=450)
hook.bind("k", lambda: print("tap"),  config=th.tap)
hook.bind("k", lambda: print("hold"), config=th.hold)
```

#### Push-to-talk (press = ON, release = OFF)

```python
from keybinds.presets import ptt

p = ptt(suppress=True)  # suppress while held (WHILE_ACTIVE)
hook.bind("v", lambda: print("PTT ON"),  config=p.press)
hook.bind("v", lambda: print("PTT OFF"), config=p.release)
```

#### Mouse auto-fire (repeat while held)

```python
from keybinds.presets import game_autofire

hook.bind_mouse(
    "left",
    lambda: print("tick"),
    config=game_autofire(delay_ms=150, interval_ms=60, suppress=True),
)
```

### Config composition

Use operators to combine configs:

* `+` → apply only changed fields (patch)
* `|` → overwrite everything (force)

```python
cfg = presets.ignore_injected() + BindConfig(suppress=SuppressPolicy.WHILE_ACTIVE)
cfg = cfg | BindConfig(suppress=SuppressPolicy.NEVER)
```

# Timing Configuration

```python
Timing(
    hold_ms=400,               # time (ms) the key must be held before ON_HOLD fires

    repeat_delay_ms=200,       # delay (ms) after press before ON_REPEAT starts
    repeat_interval_ms=80,     # interval (ms) between repeat ticks while held

    double_tap_window_ms=300,  # max time (ms) between two presses to count as a double tap

    window_focus_cache_ms=50,  # how long (ms) the active window is cached (fewer OS checks, better performance)

    chord_timeout_ms=500,      # max time (ms) allowed to finish a chord/sequence before it resets

    cooldown_ms=100,           # minimum time (ms) after a trigger during which new triggers are ignored (anti-spam)

    debounce_ms=0              # ignore events occurring too close together (filters key bounce/noise)
)
```

---

# FAQ

## ❓ What platforms are supported?

Windows only.
Uses low-level WinAPI hooks via [winput](https://github.com/Zuzu-Typ/winput).

---

## ❓ What’s the difference between `ON_RELEASE` and `ON_CHORD_RELEASED`?

### ON_RELEASE

Fires when **any key in the chord is released** after it was fully pressed.

Example:

```
Ctrl down
E down (full)
E up → fires
```

### ON_CHORD_RELEASED

Fires only when **all chord keys are released**.

Example:

```
Ctrl down
E down
E up → no
Ctrl up → fires
```

Use:

* `ON_RELEASE` → immediate reaction
* `ON_CHORD_RELEASED` → finished gesture

---

## ❓ Why do some keys (like "\`") fail to parse?

Key expressions are token-based. Letters/digits work out of the box, but punctuation often maps to OEM keys (layout-dependent).
If you need them, add a mapping for that token -> `register_key_token(name, vk)`.

---

## ❓ Why can input feel laggy sometimes?

Common causes:

* heavy callbacks (sleep/IO/printing too much)
* too many repeat events
* blocking inside hook

Keep callbacks fast and lightweight.

---

## ❓ Can suppress break my input (mouse stops clicking / keys feel blocked)?

Yes — suppression is powerful.

- `SuppressPolicy.WHEN_MATCHED` is the safest default.
- Avoid `SuppressPolicy.ALWAYS` unless you know exactly what you're doing.
- For mouse `ON_RELEASE` binds, some apps require suppressing both DOWN and the matching UP to fully block a click.

---

## ❓ Are callbacks threaded?

Yes.
Callbacks are executed outside the low-level hook to avoid input lag.
Avoid shared mutable state or protect it with locks.

---

## ❓ Can I dynamically enable/disable binds?

Yes.
You can keep references to `Bind` / `MouseBind` objects and register/unregister them manually via the `Hook`.

---

# Best Practices

✅ Keep callbacks short
✅ Use timing configs for UX
✅ Prefer `WHEN_MATCHED` suppress
❌ Avoid blocking/sleeping inside callbacks

---

# License

MIT License

---

# Third-party components

This project bundles a modified copy of **[winput](https://github.com/Zuzu-Typ/winput)**
Copyright (c) 2017 Zuzu_Typ
Licensed under the zlib/libpng license.

Changes made:
- x64 hook ABI fixes
- proper WINFUNCTYPE callbacks
- correct WinAPI signatures
- **injected / lower_il_injected detection**

The original license text is included in `keybinds/winput/LICENSE`.

---

# Contributing

PRs and issues are welcome:

* bug fixes
* performance improvements
* new triggers
* documentation
* examples

---

# ⭐ If you like it

Star the repo — it helps a lot.
