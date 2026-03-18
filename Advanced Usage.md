# Advanced Usage

This document covers features and usage patterns that are useful in real applications but more detailed than the main README.

For the experimental logical-input APIs, see **[Logical Binds and Abbreviations.md](./Logical%20Binds%20and%20Abbreviations.md)**.

For event-level debugging and tracing, see **[Diagnostics.md](./Diagnostics.md)**.

## Contents

- [1) When to use this document](#1-when-to-use-this-document)
- [2) Working with `Hook` directly](#2-working-with-hook-directly)
- [3) Registering binds programmatically](#3-registering-binds-programmatically)
- [4) Hook lifecycle and hook chain limitations](#4-hook-lifecycle-and-hook-chain-limitations)
- [4.1) Hook chain limitations and `reinstall_hooks()`](#41-hook-chain-limitations-and-reinstall_hooks)
- [5) Decorators and created bind handles](#5-decorators-and-created-bind-handles)
- [6) Unbinding](#6-unbinding)
- [7) Multiple hooks](#7-multiple-hooks)
- [8) Trigger semantics](#8-trigger-semantics)
- [9) Policies and advanced configuration](#9-policies-and-advanced-configuration)
- [10) Window-scoped binds (`hwnd`)](#10-window-scoped-binds-hwnd)
- [11) Checks / predicates and `InputState`](#11-checks--predicates-and-inputstate)
- [12) Callback execution model (workers + async)](#12-callback-execution-model-workers--async)
- [13) Injected input behavior](#13-injected-input-behavior)
- [14) Keyboard expression grammar and token parsing](#14-keyboard-expression-grammar-and-token-parsing)
- [15) Experimental logical and text APIs](#15-experimental-logical-and-text-apis)
- [16) Diagnostics and troubleshooting](#16-diagnostics-and-troubleshooting)
- [17) Performance notes](#17-performance-notes)

---

## 1) When to use this document

Use this document when you need more than the quick-start API.

Typical cases:
- you want to manage one or more `Hook` objects directly
- you need explicit bind handles and manual unbind logic
- you are mixing default-hook helpers with custom hooks
- you need suppression, injected-input, timing, or callback-policy details
- you are debugging why a bind fired or did not fire

---

## 2) Working with `Hook` directly

For non-trivial applications, it is usually better to keep an explicit `Hook` object rather than relying only on the default hook.

```python
from keybinds.bind import Hook

hook = Hook()
hook.bind("ctrl+e", lambda: print("Inventory"))
hook.join()
```

Using your own hook gives you explicit control over:
- lifecycle (`start()`, `stop()`, `join()`, `close()`)
- manual registration and unregistration
- ownership when multiple hooks exist

### Manual start

```python
from keybinds.bind import Hook

hook = Hook(auto_start=False)
hook.bind("f1", lambda: print("hello"))

hook.start()
hook.join()
```

### Context manager

```python
from keybinds.bind import Hook

with Hook() as hook:
    hook.bind("esc", hook.stop)
    hook.join()
```

### Pause / resume

```python
hook.pause()
# callbacks will not run
hook.resume()
```

Context manager form:

```python
with hook.paused():
    do_sensitive_stuff()
```

---

## 3) Registering binds programmatically

### Stable APIs

```python
hook.bind("ctrl+e", callback)
hook.bind_mouse("left", callback)
```

### Experimental logical/text APIs

```python
hook.bind_logical("ctrl+A", callback)
hook.bind_text("hello", callback)
hook.add_abbreviation("brb", "be right back")
```

Use these APIs for different problems:
- `bind(...)` — key expressions based on the regular keyboard bind model
- `bind_mouse(...)` — mouse buttons
- `bind_logical(...)` — layout-aware logical key matching
- `bind_text(...)` — typed text matching
- `add_abbreviation(...)` — text expansion

For full details on logical/text matching, see **[Logical Binds and Abbreviations.md](./Logical%20Binds%20and%20Abbreviations.md)**.

---

## 4) Hook lifecycle and hook chain limitations

### Basic lifecycle methods

```python
hook.stop()   # signal wait()/join() to exit
hook.close()  # detach this frontend + stop callback workers
```

### `wait(timeout)` for polling

```python
if not hook.wait(timeout=0.5):
    print("still running...")
```

### `join()`

`hook.join()` blocks until stopped, then closes the hook frontend.

### Why hook order matters

On Windows, low-level hook suppression depends on the global hook chain order.
If another hook is installed after yours, that later hook may observe the event first and may affect what your process can suppress or observe.

This is not specific to `keybinds`; it is a property of the Windows low-level hook chain.

## 4.1) Hook chain limitations and `reinstall_hooks()`

If suppression or delivery changes after another tool installs its own low-level hooks, you can force `keybinds` to reinstall its hooks:

```python
hook.reinstall_hooks()
```

This is useful when:
- another program installed low-level keyboard or mouse hooks after your process
- suppression behavior changed unexpectedly
- you want `keybinds` to re-enter the hook chain later

Important notes:
- this is a best-effort workaround, not a guarantee
- hook order can still change again later
- this should not be needed during normal use

---

## 5) Decorators and created bind handles

Decorators attach created bind handles to the function.

- `func.binds` always contains a list of all created bind objects
- `func.bind` is kept as a compatibility alias:
  - single bind → `func.bind` is that bind object
  - multiple binds → `func.bind` is a list of bind objects

This applies to keyboard, mouse, logical, text, and abbreviation decorators.

```python
from keybinds.decorators import bind_key, bind_mouse

@bind_key(["ctrl+a", "ctrl+b"], hook=hook)
@bind_mouse(["left", "right"], hook=hook)
def action():
    print("action")

print(action.binds)
```

This is mainly useful when you intentionally want to manage decorator-created binds manually.

---

## 6) Unbinding

The easiest API is the unified `unbind(...)` method.

It accepts:
- a single bind object
- a decorated function
- `func.bind`
- `func.binds`
- an iterable of bind objects

```python
hook.unbind(action)
hook.unbind(action.binds)
hook.unbind(action.bind)
hook.unbind(some_bind)
```

Top-level helper form:

```python
import keybinds

keybinds.unbind(action)
```

### Important behavior

- `func.binds` is the source of truth
- `func.bind` is a compatibility alias
- after unbinding, both are updated to reflect the remaining active binds

This means:
- no remaining binds → `func.binds == []`, `func.bind is None`
- one remaining bind → `func.bind` is that bind object
- multiple remaining binds → `func.bind` is a list

---

## 7) Multiple hooks

Multiple hooks are supported.

```python
hook1 = Hook()
hook2 = Hook()
```

This is useful when you want separate lifecycle or ownership boundaries.

### Ownership model

Every bind object keeps a reference to its owning hook.
A hook only unregisters bind objects that it owns.

A bind object cannot be registered into two different hooks at the same time.

### Practical recommendation

If you use multiple hooks, prefer explicit unbinding through the owning hook:

```python
hook1.unbind(my_callback)
```

Top-level helpers such as `keybinds.bind_key(...)` and `keybinds.unbind(...)` operate through the default hook. They are convenient, but less explicit in multi-hook applications.

---

## 8) Trigger semantics

### `ON_PRESS` vs `ON_CHORD_COMPLETE`

For a single chord such as `ctrl+e`:
- `ON_PRESS` fires on a fresh keydown while the chord is full
- `ON_CHORD_COMPLETE` fires only on the transition from not-full to full

```python
from keybinds.types import BindConfig, Trigger

hook.bind(
    "ctrl+e",
    callback,
    config=BindConfig(trigger=Trigger.ON_CHORD_COMPLETE),
)
```

Use `ON_CHORD_COMPLETE` when you want one fire per full chord completion instead of one fire per fresh keydown.

### `ON_RELEASE` vs `ON_CHORD_RELEASED`

For chords:
- `ON_RELEASE` fires when any chord key is released after completion
- `ON_CHORD_RELEASED` fires only when all chord keys are released after completion

### Sequence triggers

For sequence expressions, the most readable trigger is usually `Trigger.ON_SEQUENCE`.

```python
from keybinds.types import BindConfig, Trigger, Timing

hook.bind(
    "g,k,i",
    callback,
    config=BindConfig(
        trigger=Trigger.ON_SEQUENCE,
        timing=Timing(chord_timeout_ms=600),
    ),
)
```

`Timing.chord_timeout_ms` is also used as the inter-step timeout for sequences.

---

## 9) Policies and advanced configuration

The main advanced behavior knobs live in `BindConfig`, especially `constraints`, timing fields, suppression, injected-input handling, and focus behavior.

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


## `Constraints.allow_os_key_repeat`

Whether OS-generated repeated **keydown** events (while a key is held) are treated as fresh presses.

* `False` (default) — ignore OS key-repeat.
* `True` — allow OS key-repeat (e.g., `ON_PRESS` may fire repeatedly).

```python
from keybinds.types import BindConfig, Constraints

cfg = BindConfig(constraints=Constraints(allow_os_key_repeat=True))
hook.bind("g", lambda: print("repeat!"), config=cfg)
```

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

### Policy reference (suppress / injected / chord / order)

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

### `FocusPolicy`
Controls what happens to bind runtime state when a window-scoped bind (`hwnd=...`) loses focus.

- `CANCEL_ON_BLUR` — reset the bind state on focus loss (default). This cancels active hold/repeat cycles, sequence progress, tap counters, and chord progress.
- `PAUSE_ON_BLUR` — pause active repeat/hold behavior on blur without a full reset, so matching can continue/resume when focus returns depending on trigger and current input state.

Typical choice: `CANCEL_ON_BLUR` for predictable app/window-local hotkeys.

### Combining policies

These policies are orthogonal:

- `SuppressPolicy` → event blocking
- `InjectedPolicy` → physical vs synthetic filtering
- `ChordPolicy` → extra-key tolerance
- `OrderPolicy` → press order requirements
- `FocusPolicy` → blur behavior for window-scoped binds

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
        focus=FocusPolicy.CANCEL_ON_BLUR,          # default for window-scoped binds (hwnd=...)
        constraints=Constraints(
            chord_policy=ChordPolicy.IGNORE_EXTRA_MODIFIERS,  # tolerate extra modifiers
            order_policy=OrderPolicy.STRICT_RECOVERABLE,      # ordered chord with recoverable tail rebuild
        ),
    ),
)
```

---


## 10) Window-scoped binds (`hwnd`)

Keyboard and mouse binds accept an optional `hwnd`.
When provided, the bind only evaluates while that window is focused.

```python
hook.bind("ctrl+e", callback, hwnd=target_hwnd)
```

`Timing.window_focus_cache_ms` controls how often the active-window check is refreshed.

```python
from keybinds.types import BindConfig, Timing

cfg = BindConfig(timing=Timing(window_focus_cache_ms=25))
hook.bind("ctrl+e", callback, config=cfg, hwnd=target_hwnd)
```

---

## 11) Checks / predicates and `InputState`

Predicates let you add custom conditions around bind firing.

`InputState` exposes the current observed input state, including pressed keys and mouse buttons.

Typical uses:
- require or forbid a mode flag from your application
- inspect currently pressed keys
- gate behavior on additional state that is not expressible in the key grammar

If you are debugging state transitions, see **[Diagnostics.md](./Diagnostics.md)**.

---

## 12) Callback execution model (workers + async)

Callbacks do not run directly inside the low-level hook procedure.
They are dispatched through workers so the hook thread can stay responsive.

Practical implications:
- keep callbacks reasonably small
- avoid blocking work on the callback path when possible
- if you need async integration, use the async helpers/examples instead of blocking the callback thread yourself

See:
- `examples/async_simple.py`
- `examples/async_advanced.py`

---

## 13) Injected input behavior

Injected input can be handled differently from physical input.
This matters for macros, `SendInput`, text expansion, and tools that synthesize keyboard or mouse events.

This behavior is controlled through bind policies.
When debugging injected events, use **[Diagnostics.md](./Diagnostics.md)** to inspect what the backend saw.

---

## 14) Keyboard expression grammar and token parsing

### Grammar

- `+` = simultaneous chord step (`ctrl+e`)
- `,` = sequence steps (`g,k,i`)
- surrounding whitespace is ignored

### Supported token categories

- letters: `a`..`z`
- digits: `0`..`9`
- function keys: `f1`..`f24`
- common keys: `esc`, `enter`, `space`, arrows, etc.
- common punctuation (OEM-based): `` ` ``, `-`, `=`, `[`, `]`, `\`, `;`, `'`, `,`, `.`, `/`
- modifier aliases: `ctrl`, `control`, `shift`, `alt`, `menu`, `win`, `lwin`, `rwin`
- side-specific modifiers: `lctrl`, `rctrl`, `lshift`, `rshift`, `lalt`, `ralt`, `left ctrl`, `right alt`, etc.
- numpad keys: `num0`..`num9`, `numpad0`..`numpad9`, `numlock`, `num/`, `num*`, `num-`, `num+`, `num.`

### Custom token registration

```python
from keybinds import register_key_token

register_key_token("grave_ansi", 0xC0)
```

Then use it in expressions:

```python
hook.bind("ctrl+grave_ansi", callback)
```

---

## 15) Experimental logical and text APIs

These APIs are currently experimental:
- `bind_logical(...)`
- `bind_text(...)`
- `add_abbreviation(...)`
- logical/text decorators and helpers

Use them when you need:
- layout-aware logical key matching
- text-stream matching
- text expansion / abbreviations

Do not use them as a replacement for ordinary hotkeys unless you specifically need logical/text behavior.

See **[Logical Binds and Abbreviations.md](./Logical%20Binds%20and%20Abbreviations.md)** for full details.

---

## 16) Diagnostics and troubleshooting

If a bind does not fire as expected, start with diagnostics.

Use **[Diagnostics.md](./Diagnostics.md)** when you need to inspect:
- what events the backend received
- which stage rejected a bind
- whether input was injected
- why suppression did or did not happen

If the issue is specific to logical/text matching, also see **[Developer Notes - Logical.md](./Developer%20Notes%20-%20Logical.md)**.

---

## 17) Performance notes

Measured using `examples/benchmark.py` on one test system and Python build, so these numbers should be treated as a rough reference rather than a guaranteed baseline.

- p50 ≈ 0.29 ms
- p99 ≈ 0.48 ms
- max < 0.8 ms (rare spikes up to 3–5 ms)

Latency includes hook dispatch and callback scheduling (no heavy user code).
