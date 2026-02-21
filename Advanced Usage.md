# Advanced Usage

This document covers advanced features and implementation-aware usage patterns of `keybinds` that are useful in real applications but too detailed for the main README.

## Contents

- [1) Trigger semantics (important differences)](#1-trigger-semantics-important-differences)
- [2) Keyboard expression grammar and token parsing](#2-keyboard-expression-grammar-and-token-parsing)
- [3) Window-scoped binds (`hwnd`)](#3-window-scoped-binds-hwnd)
- [4) Hook lifecycle, default hook, and multiple Hook instances](#4-hook-lifecycle-default-hook-and-multiple-hook-instances)
- [5) Callback execution model (workers + async)](#5-callback-execution-model-workers--async)
- [6) Advanced constraints and timing](#6-advanced-constraints-and-timing)
- [7) Policy reference (suppress / injected / chord / order)](#7-policy-reference-suppress--injected--chord--order)
- [8) Checks / predicates and `InputState`](#8-checks--predicates-and-inputstate)
- [9) Injected-input behavior (macros / SendInput)](#9-injected-input-behavior-macros--sendinput)
- [10) Advanced presets and profiles](#10-advanced-presets-and-profiles)
- [11) Config composition (`+` and `|`)](#11-config-composition--and-)
- [12) Decorators: advanced patterns](#12-decorators-advanced-patterns)
- [13) Keyboard vs mouse support matrix](#13-keyboard-vs-mouse-support-matrix)

---

## 1) Trigger semantics (important differences)

### `ON_PRESS` vs `ON_CHORD_COMPLETE`
For a **single chord** (e.g. `ctrl+e`):

- `ON_PRESS` fires on a fresh keydown **while the chord is full**
- `ON_CHORD_COMPLETE` fires only on the transition **NOT_FULL -> FULL**

This matters when modifiers are held and non-modifier keys are tapped repeatedly.

#### Example
```python
from keybinds.types import BindConfig, Trigger

hook.bind(
    "ctrl+e",
    lambda: print("complete"),
    config=BindConfig(trigger=Trigger.ON_CHORD_COMPLETE),
)
````

Use `ON_CHORD_COMPLETE` when you want one trigger per chord completion, not every fresh keydown while the chord remains full.

---

### `ON_RELEASE` vs `ON_CHORD_RELEASED`

For chords:

* `ON_RELEASE` fires when **any chord key** is released **after** the chord has been fully pressed
* `ON_CHORD_RELEASED` fires only when **all chord keys** are released after completion

#### Example

```python
from keybinds.types import BindConfig, Trigger

hook.bind("ctrl+e", lambda: print("any release"),
          config=BindConfig(trigger=Trigger.ON_RELEASE))

hook.bind("ctrl+e", lambda: print("all released"),
          config=BindConfig(trigger=Trigger.ON_CHORD_RELEASED))
```

---

### Sequences (`g,k,i`) and triggers

For sequence expressions, the engine treats these as valid “final-step fire” triggers:

* `Trigger.ON_SEQUENCE`
* `Trigger.ON_PRESS`
* `Trigger.ON_CHORD_COMPLETE`

In practice, prefer `ON_SEQUENCE` for readability.

```python
from keybinds.types import BindConfig, Trigger, Timing

hook.bind(
    "g,k,i",
    lambda: print("secret"),
    config=BindConfig(
        trigger=Trigger.ON_SEQUENCE,
        timing=Timing(chord_timeout_ms=600),
    ),
)
```

> `Timing.chord_timeout_ms` is used as the **inter-step timeout** for sequences as well.

---

## 2) Keyboard expression grammar and token parsing

### Grammar

* `+` = simultaneous chord step (`ctrl+e`)
* `,` = sequence steps (`g,k,i`)
* whitespace around tokens is ignored

### Supported token categories

* letters: `a`..`z`
* digits: `0`..`9`
* function keys: `f1`..`f24`
* common keys: `esc`, `enter`, `space`, arrows, etc.
* common punctuation (OEM-based): `` ` ``, `-`, `=`, `[`, `]`, `\`, `;`, `'`, `,`, `.`, `/`
* modifier aliases: `ctrl`, `control`, `shift`, `alt`, `menu`, `win`, `lwin`, `rwin`

### Custom token registration

If your layout or preferred name is not covered:

```python
from keybinds import register_key_token

# name is case-insensitive
register_key_token("grave_ansi", 0xC0)
```

Then you can use it in expressions:

```python
hook.bind("ctrl+grave_ansi", callback)
```

---

## 3) Window-scoped binds (`hwnd`)

Both keyboard and mouse binds accept an optional `hwnd` parameter.
When provided, the bind only evaluates while that window is focused.

```python
import ctypes
from ctypes import wintypes
from keybinds.bind import Hook

user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.GetForegroundWindow.argtypes = ()
user32.GetForegroundWindow.restype = wintypes.HWND

target_hwnd = int(user32.GetForegroundWindow())

hook = Hook()
hook.bind("ctrl+e", lambda: print("Only this window"), hwnd=target_hwnd)
hook.join()
```

### Focus check caching

`Timing.window_focus_cache_ms` controls how often the active-window check is refreshed (performance optimization).

```python
from keybinds.types import BindConfig, Timing

cfg = BindConfig(timing=Timing(window_focus_cache_ms=25))
hook.bind("ctrl+e", callback, config=cfg, hwnd=target_hwnd)
```

---

## 4) Hook lifecycle, default hook, and multiple Hook instances

## Basic lifecycle methods

```python
from keybinds.bind import Hook

hook = Hook()
# ... add binds ...
hook.stop()        # signal wait()/join() to exit
hook.close()       # detach this frontend + stop callback workers
```

### `wait(timeout)` for polling

```python
if not hook.wait(timeout=0.5):
    print("still running...")
```

### `join()`

`hook.join()` blocks until stopped, then closes the hook frontend.

---

## Pause / resume without unregistering binds

Useful when your app has modes (e.g. chat open vs gameplay):

```python
hook.pause()
# no callbacks will fire
hook.resume()
```

Context manager form:

```python
with hook.paused():
    # temporarily disabled
    do_sensitive_stuff()
```

Pause is reference-counted internally, so nested pauses are safe.

---

### Context manager support

`Hook` can be used as a context manager.

```python
from keybinds.bind import Hook

with Hook() as hook:
    hook.bind("esc", lambda: hook.stop())
    hook.join()
```

Behavior:

* `__enter__` — starts the dispatcher if it was stopped.
* `__exit__` — calls `close()` automatically.

This is equivalent to manually calling `close()` at the end of the lifecycle.

---

## Dynamic bind management (`unbind` / `unbind_mouse`)

```python
b = hook.bind("f1", lambda: print("temp"))
hook.unbind(b)

m = hook.bind_mouse("left", lambda: print("temp mouse"))
hook.unbind_mouse(m)
```

This is the recommended way to enable/disable features dynamically.

---

## Default hook (used by decorators)

Decorators create/register binds on a shared default hook.

```python
import keybinds
from keybinds.bind import Hook

custom = Hook()
keybinds.set_default_hook(custom)
```

Now decorators without `hook=...` will attach to `custom`.

---

## Multiple `Hook()` instances in one process

You can create multiple Hook frontends. Internally, the library uses a **single process-wide backend** that installs low-level hooks once and dispatches events to all active `Hook` instances.

This is useful for:

* plugin/module isolation
* temporary feature groups
* independent pause/unpause domains

---

## 5) Callback execution model (workers + async)

## Worker pool (`callback_workers`)

Callbacks are executed outside the low-level hook path via a small worker pool.

```python
hook = Hook(callback_workers=4)
```

Use more than 1 worker if callbacks may block briefly and you want higher throughput.

> Be careful with shared state (locks / queues / thread-safe structures).

---

## Async callbacks and `asyncio`

If a callback returns an awaitable (e.g. `async def` function), `keybinds` schedules it on an asyncio event loop.

### Use library-managed loop

```python
hook = Hook()  # loop is created lazily when needed
```

### Use your own loop

```python
hook = Hook(asyncio_loop=my_running_loop)
```

If you pass your own loop, you are responsible for running it.

---

## Async exception handler (`on_async_error`)

Provide a custom handler for async callback exceptions:

```python
def on_async_error(exc: BaseException) -> None:
    print("Async callback failed:", exc)

hook = Hook(on_async_error=on_async_error)
```

Without a custom handler, errors are printed by the library.

---

## 6) Advanced constraints and timing

## `Constraints.chord_policy`

### `IGNORE_EXTRA_MODIFIERS` (default)

Allows extra modifiers beyond the required chord keys.

This is usually the best UX default.

### `STRICT`

Requires exact chord membership (except keys explicitly ignored via `ignore_keys`).

```python
from keybinds.types import BindConfig, Constraints, ChordPolicy

cfg = BindConfig(
    constraints=Constraints(chord_policy=ChordPolicy.STRICT)
)
hook.bind("ctrl+shift+u", callback, config=cfg)
```

### `RELAXED`

Only checks that required groups are present; extra keys are tolerated.

---

## `Constraints.ignore_keys` (strict-mode escape hatch)

In strict mode, allow specific extra VK codes to be ignored.

```python
from keybinds import winput
from keybinds.types import BindConfig, Constraints, ChordPolicy

cfg = BindConfig(
    constraints=Constraints(
        chord_policy=ChordPolicy.STRICT,
        ignore_keys={winput.VK_CAPITAL},  # e.g. Caps Lock state/key
    )
)
hook.bind("ctrl+e", callback, config=cfg)
```

---

### `Constraints.order_policy`

Controls whether chord keys must be pressed in the defined order.

* `OrderPolicy.ANY` (default) — order does not matter.
* `OrderPolicy.STRICT` — any order violation invalidates the whole chord cycle until all chord keys are released.
* `OrderPolicy.STRICT_RECOVERABLE` — ordered matching with recoverable tail rebuild after the first full match.

Applies only to keyboard chords.

```python
from keybinds.types import BindConfig, Constraints, OrderPolicy

hook.bind(
    "ctrl+shift+x",
    callback,
    config=BindConfig(
        constraints=Constraints(order_policy=OrderPolicy.STRICT_RECOVERABLE)
    ),
)
```

Example (`ctrl+shift+x`):

* Valid: `Ctrl → Shift → X`
* Invalid in `STRICT`: `Shift → Ctrl → X`
* In `STRICT_RECOVERABLE`, tail rebuild mistakes after first match are recoverable while the prefix remains held.

---

## `Constraints.max_fires`

Cap how many times a bind can fire in its lifetime.

```python
from keybinds.types import BindConfig, Constraints

cfg = BindConfig(constraints=Constraints(max_fires=1))
hook.bind("f12", lambda: print("one-shot"), config=cfg)
```

Use this for:

* one-shot actions
* onboarding hints
* temporary unlocks

---

## Timing knobs (advanced notes)

```python
from keybinds.types import Timing

Timing(
    hold_ms=400,
    repeat_delay_ms=200,
    repeat_interval_ms=80,
    double_tap_window_ms=300,
    window_focus_cache_ms=50,
    chord_timeout_ms=500,
    cooldown_ms=100,
    debounce_ms=0,
)
```

### Practical usage tips

* `cooldown_ms`: anti-spam (especially for repeat / double tap edge cases)
* `debounce_ms`: keyboard event noise filtering / bounce-like behavior
* `window_focus_cache_ms`: only matters when `hwnd` is used
* `chord_timeout_ms`: also affects sequence step timeout

---

## 7) Policy reference (suppress / injected / chord / order)

These policies are configured via `BindConfig` / `MouseBindConfig` and can be combined independently.

### `SuppressPolicy`
Controls whether input is blocked from reaching Windows / other apps.

- `NEVER` — never suppress.
- `WHEN_MATCHED` — suppress only when the bind matches/fires.
- `WHILE_ACTIVE` — suppress while the bind is active (useful for hidden chords / hold patterns).
- `WHILE_EVALUATING` — suppress while the matcher evaluates current input.
- `ALWAYS` — always suppress the matching input path.

Typical choice: `WHEN_MATCHED`.

### `InjectedPolicy`
Controls handling of synthetic input (`SendInput`, macros, automation tools).

- `ALLOW` — handle physical + injected input.
- `IGNORE` — ignore injected input.
- `ONLY` — react only to injected input.

Typical choice: `IGNORE` for physical-only hotkeys.

### `ChordPolicy`
Controls how extra keys are treated while matching keyboard chords.

- `IGNORE_EXTRA_MODIFIERS` — allows extra modifier keys (default; best general UX).
- `STRICT` — exact chord match (except keys in `ignore_keys`).
- `RELAXED` — extra keys are tolerated if required chord groups are present.

Typical choice: `IGNORE_EXTRA_MODIFIERS`.

### `OrderPolicy`
Controls whether keyboard chord keys must be pressed in the defined order.

- `ANY` — order does not matter (default).
- `STRICT` — any order violation invalidates the chord cycle until all chord keys are released.
- `STRICT_RECOVERABLE` — ordered matching with recoverable tail rebuild after the first full match.

Applies only to keyboard chords (not sequences, not mouse binds).

### Combining policies

These policies are orthogonal:

- `SuppressPolicy` → event blocking
- `InjectedPolicy` → physical vs synthetic filtering
- `ChordPolicy` → extra-key tolerance
- `OrderPolicy` → press order requirements

```python
from keybinds.types import (
    BindConfig,
    Constraints,
    SuppressPolicy,
    InjectedPolicy,
    ChordPolicy,
    OrderPolicy,
)

hook.bind(
    "ctrl+shift+x",
    callback,
    config=BindConfig(
        suppress=SuppressPolicy.WHEN_MATCHED,      # block only on successful match
        injected=InjectedPolicy.IGNORE,            # physical input only
        constraints=Constraints(
            chord_policy=ChordPolicy.IGNORE_EXTRA_MODIFIERS,  # tolerate extra modifiers
            order_policy=OrderPolicy.STRICT_RECOVERABLE,      # ordered chord with recoverable tail rebuild
        ),
    ),
)
```

---

## 8) Checks / predicates and `InputState`

## Predicate signature

A predicate receives `(event, state)` and should return `True` / `False`.

```python
def my_check(event, state) -> bool:
    return True
```

You can pass:

* a single callable
* a list/tuple of callables
* `Checks([...])`

---

## `InputState` fields (useful in predicates)

The state object exposes separate domains:

* `pressed_keys` / `pressed_mouse` → physical (non-injected) only
* `pressed_keys_all` / `pressed_mouse_all` → physical + injected
* `pressed_keys_injected` / `pressed_mouse_injected` → injected only

Example: only fire when **physical Ctrl** is held:

```python
from keybinds import winput
from keybinds.types import BindConfig

def phys_ctrl_held(event, state):
    return (
        winput.VK_CONTROL in state.pressed_keys
        or winput.VK_LCONTROL in state.pressed_keys
        or winput.VK_RCONTROL in state.pressed_keys
    )

hook.bind("e", callback, config=BindConfig(checks=phys_ctrl_held))
```

> Treat `event` and `state` as read-only inside predicates/callbacks.

---

## 9) Injected-input behavior (macros / SendInput)

`InjectedPolicy` controls whether synthetic input is processed:

* `ALLOW` → both physical and injected
* `IGNORE` → ignore injected completely
* `ONLY` → only injected

```python
from keybinds.types import BindConfig, InjectedPolicy

hook.bind("f8", callback, config=BindConfig(injected=InjectedPolicy.ONLY))
```

### Practical patterns

* Ignore macro spam:

  ```python
  BindConfig(injected=InjectedPolicy.IGNORE)
  ```
* Build automation bridges / test harnesses:

  ```python
  BindConfig(injected=InjectedPolicy.ONLY)
  ```

---

## 10) Advanced presets and profiles

Besides the basic presets in the README, `keybinds.presets` also provides a larger set.

## Keyboard presets

* `press(...)`
* `release(...)`
* `chord_released(...)`
* `click(...)`
* `hold(...)`
* `repeat(...)`
* `double_tap(...)`
* `sequence(...)`

## Mouse presets

* `mouse_press(...)`
* `mouse_release(...)`
* `mouse_click(...)`
* `mouse_hold(...)`
* `mouse_repeat(...)`
* `mouse_double_tap(...)`

## Helpers

* `timing(...)`
* `strict_constraints()`
* `suppress(mouse=False)`
* `ignore_injected(mouse=False)`

## Profiles

* `tap_hold(...)` → returns `.tap` and `.hold`
* `ptt(...)` → returns `.press` and `.release`
* `silent_hotkey(...)`
* `hidden_chord(...)`
* `game_autofire(...)`
* `rapid_double_tap(...)`
* `cheatcode_sequence(...)`

### Example: push-to-talk

```python
from keybinds.presets import ptt

p = ptt(suppress=True)

hook.bind("v", lambda: print("PTT ON"),  config=p.press)
hook.bind("v", lambda: print("PTT OFF"), config=p.release)
```

### Example: hidden chord (suppress while assembling)

```python
from keybinds.presets import hidden_chord

hook.bind("ctrl+shift+x", callback, config=hidden_chord(strict=True))
```

---

## 11) Config composition (`+` and `|`)

`BindConfig` and `MouseBindConfig` support operator-based composition.

## `+` = soft merge (patch semantics)

Only non-default fields from the right-hand config are applied.

```python
from keybinds.types import BindConfig, SuppressPolicy
from keybinds.presets import repeat

cfg = repeat(delay_ms=180, interval_ms=60) + BindConfig(
    suppress=SuppressPolicy.WHILE_ACTIVE
)
```

## `|` = hard merge (full override semantics)

All fields from the right-hand config overwrite left-hand fields (including defaults).

```python
cfg = cfg | BindConfig(suppress=SuppressPolicy.NEVER)
```

### Rule of thumb

* Use `+` to tweak a preset
* Use `|` when you intentionally want to reset/replace fields

---

## 12) Decorators: advanced patterns

## Explicit hook

```python
from keybinds.bind import Hook
from keybinds.decorators import bind_key

hook = Hook()

@bind_key("ctrl+e", hook=hook)
def inventory():
    print("Inventory")
```

## Window-scoped decorator bind

```python
@bind_key("f1", hwnd=target_hwnd)
def local_to_window():
    ...
```

## Legacy convenience flags (`bind_key`)

If `config` is not provided, `bind_key` can build a simple config from:

* `trigger_on_release=True`
* `suppress=True`

```python
@bind_key("ctrl+r", suppress=True)
def reload():
    ...
```

---

## Mouse decorator with multiple buttons (single callback)

`bind_mouse` can accept a list and creates one bind per button.

```python
from keybinds.decorators import bind_mouse

@bind_mouse(["left", "right"])
def both_buttons():
    print("LMB or RMB")
```

### Accessing created bind handles

Decorators attach bind handle(s) to the function as `func.bind`.

* single bind → `func.bind` is a `Bind` / `MouseBind`
* multiple mouse buttons → `func.bind` is a list of `MouseBind`

```python
hook.unbind_mouse(both_buttons.bind[0])
```

(Only do this if you intentionally want to manage decorator-created binds manually.)

---

## 13) Keyboard vs mouse support matrix

## Triggers

| Trigger             | Keyboard | Mouse |
| ------------------- | -------: | ----: |
| `ON_PRESS`          |        ✅ |     ✅ |
| `ON_RELEASE`        |        ✅ |     ✅ |
| `ON_CLICK`          |        ✅ |     ✅ |
| `ON_HOLD`           |        ✅ |     ✅ |
| `ON_REPEAT`         |        ✅ |     ✅ |
| `ON_DOUBLE_TAP`     |        ✅ |     ✅ |
| `ON_CHORD_COMPLETE` |        ✅ |    🚫 |
| `ON_CHORD_RELEASED` |        ✅ |    🚫 |
| `ON_SEQUENCE`       |        ✅ |    🚫 |

## Expression types

| Feature             | Keyboard | Mouse |
| ------------------- | -------: | ----: |
| Single key/button   |        ✅ |     ✅ |
| Chords (`a+b`)      |        ✅ |    🚫 |
| Sequences (`a,b,c`) |        ✅ |    🚫 |
