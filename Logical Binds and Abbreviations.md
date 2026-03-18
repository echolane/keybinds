# Logical Binds and Abbreviations

This document covers the experimental logical-input layer in `keybinds`:

- `LogicalBind`
- `hook.bind_logical(...)`
- `hook.bind_text(...)`
- `hook.add_abbreviation(...)`
- helper function: `add_abbreviation(...)`
- decorator helpers: `bind_logical(...)`, `bind_text(...)`, `bind_abbreviation(...)`
- `LogicalConfig` and related policies

Unlike normal keyboard binds, logical binds match **produced characters and typed text**, not just static VK key names.
That makes them useful for layout-aware shortcuts, text-driven triggers, and abbreviations.

> **Experimental:** logical binds and text abbreviations are currently experimental.
> The API is usable, but edge cases around layout switching, dead keys, IME/input-method behavior, editor-specific key handling, and unusual keyboard drivers may still change in future releases.

If you are trying to understand why a normal VK-based bind fired or did not fire, see **[Advanced Usage.md](./Advanced%20Usage.md)** and **[Diagnostics.md](./Diagnostics.md)**.

If you are modifying the logical-input implementation itself, see **[Developer Notes - Logical.md](./Developer%20Notes%20-%20Logical.md)**.

---

## Contents

- [1) What “logical” means](#1-what-logical-means)
- [2) When to use normal binds vs logical binds](#2-when-to-use-normal-binds-vs-logical-binds)
- [3) Quick start](#3-quick-start)
- [4) `bind_logical(...)`](#4-bind_logical)
- [5) `bind_text(...)`](#5-bind_text)
- [6) `add_abbreviation(...)`](#6-add_abbreviation)
- [7) `bind_abbreviation(...)`](#7-bind_abbreviation)
- [7) Expression grammar for logical binds](#7-expression-grammar-for-logical-binds)
- [8) `LogicalConfig`](#8-logicalconfig)
- [9) Text matching policies](#9-text-matching-policies)
- [10) Replacement behavior for abbreviations](#10-replacement-behavior-for-abbreviations)
- [11) Practical examples](#11-practical-examples)
- [12) Decorator helpers](#12-decorator-helpers)
- [13) Limitations and current status](#13-limitations-and-current-status)

---

## 1) What “logical” means

A normal keyboard bind matches **physical / VK-level keys**.

For example:

```python
hook.bind("ctrl+a", callback)
```

This means “the Control modifier and the key whose VK token is `a`”.

A logical bind matches the **character that was logically produced** after the current layout and modifier state are applied.

For example:

```python
hook.bind_logical("ctrl+A", callback)
```

This means “Control plus the logical character `A`”, which may come from a different physical key depending on the active layout.

That difference is important when you care about:

- current keyboard layout
- uppercase / lowercase behavior
- `Shift`, `AltGr`, and `CapsLock`
- typed text sequences rather than static key names

---

## 2) When to use normal binds vs logical binds

Use normal `hook.bind(...)` when you want:

- stable VK-based shortcuts such as `ctrl+s`, `f5`, `alt+tab`
- physical-key semantics
- the most mature and battle-tested behavior

Use logical APIs when you want:

- shortcuts based on the **resulting character**
- layout-aware matching such as `ctrl+A`
- typed-text triggers such as `Hello!`
- abbreviations and text expansion

A good rule of thumb:

- **shortcut / hotkey** → `bind(...)` or `bind_logical(...)`
- **typed text** → `bind_text(...)`
- **text replacement** → `add_abbreviation(...)`

---

## 3) Quick start

### Logical shortcut

```python
from keybinds import Hook

hook = Hook()
hook.bind_logical("ctrl+A", lambda: print("logical shortcut"))
hook.join()
```

### Typed text trigger

```python
from keybinds import Hook

hook = Hook()
hook.bind_text("Hello!", lambda: print("typed text matched"))
hook.join()
```

### Abbreviation

```python
from keybinds import Hook

hook = Hook()
hook.add_abbreviation("brb", "be right back")
hook.add_abbreviation("omw", "on my way")
hook.join()
```

### Decorator style

```python
import keybinds
from keybinds import bind_logical, bind_text, add_abbreviation, bind_abbreviation

@bind_logical("ctrl+A")
def logical_shortcut():
    print("logical shortcut")

@bind_text("hello")
def saw_hello():
    print("typed hello")

@bind_abbreviation("brb", "be right back")
def expanded_brb():
    print("abbreviation expanded")

keybinds.join()
```

All three decorator helpers (`bind_logical`, `bind_text`, and `bind_abbreviation`) use `get_default_hook()` when `hook=` is not provided.
You can also pass `hook=custom_hook` explicitly.

---

## 4) `bind_logical(...)`

`hook.bind_logical(...)` creates a `LogicalBind`.
It is intended primarily for logical chords, punctuation, and short character-oriented sequences.

```python
hook.bind_logical("ctrl+A", callback)
hook.bind_logical(r"\,", callback)
hook.bind_logical(r"\+", callback)
```

### What it is good at

- layout-aware shortcuts
- logical punctuation such as `\,` or `\+`
- character-oriented sequences where you really want sequence semantics

### What it is **not** ideal for

For full typed-text matching, prefer `hook.bind_text(...)`.

For ordinary typed text, prefer `hook.bind_text(...)` instead of spelling out a long logical sequence.

```python
hook.bind_text("Hello!", callback)
```

`bind_text(...)` is more natural for text, handles helper keys more gracefully, and is usually the better API for words or sentences.

---

## 5) `bind_text(...)`

`hook.bind_text(text, callback, ...)` matches the recent **typed text stream**.

```python
from keybinds import Hook, LogicalConfig

hook = Hook()

hook.bind_text(
    "Hello!",
    lambda: print("hello"),
    logical_config=LogicalConfig(case_sensitive=False),
)
```

This API is useful when you want to react to actual text entry rather than to a key sequence specification.

It is usually the best choice for:

- words
- punctuation-rich strings
- layout-aware text matching
- matching text regardless of how uppercase was produced (`Shift` vs `CapsLock`), depending on configuration

---

## 6) `add_abbreviation(...)`

`hook.add_abbreviation(typed, replacement, ...)` watches the typed text stream and replaces matches.

```python
from keybinds import Hook

hook = Hook()

hook.add_abbreviation("brb", "be right back")
hook.add_abbreviation("omw", "on my way")
hook.add_abbreviation("@@", "user@example.com")
```

### Typical use cases

- short text expansions
- slang or shorthand expansion
- email / signature insertion
- punctuation-triggered expansions

### Important note

Abbreviations are text-driven, not VK-token-driven.
That means they are intended to work with the resulting typed text, even when `Shift`, `CapsLock`, or layout switching are involved.

---

## 7) Expression grammar for logical binds

Logical bind expressions follow the same top-level structure as normal keyboard expressions:

- `+` = simultaneous chord step
- `,` = sequence separator

Examples:

```python
hook.bind_logical("ctrl+A", callback)
hook.bind_logical(r"\,", callback)
```

### Escaping literal `+` and `,`

Use backslash escaping for literal punctuation that would otherwise be parsed structurally.

```python
hook.bind_logical(r"\+", callback)   # logical plus sign
hook.bind_logical(r"\,", callback)   # logical comma character
hook.bind_logical(r"\+,\,", callback)
```

### Tokens

Logical expressions can contain:

- modifier words such as `ctrl`, `shift`, `alt`, `altgr`, `win`
- common named keys such as `space`, `enter`, `tab`
- single logical characters such as `A`, `a`, `!`, `,`, `+`

For typed text, prefer `bind_text(...)` instead of writing long logical sequences by hand.

---

## 8) `LogicalConfig`

`LogicalConfig` is shared by `LogicalBind`, `bind_text(...)`, and `add_abbreviation(...)`.

Example:

```python
from keybinds import Hook, LogicalConfig

hook = Hook(
    default_logical_config=LogicalConfig(
        case_sensitive=False,
        # Often redundant when case_sensitive=False, but explicit is fine.
        respect_caps_lock=False,
    )
)
```

Per-bind override:

```python
hook.bind_text(
    "Hello!",
    callback,
    logical_config=LogicalConfig(case_sensitive=False),
)
```

### Main fields

- `case_sensitive=True`
- `respect_caps_lock=True`
- `ignore_modifier_keys=True`
- `ignore_toggle_keys=True`
- `text_ignore_ctrl_combos=True`
- `text_ignore_alt_combos=True`
- `text_ignore_win_combos=True`
- `text_clear_buffer_on_non_text=False`
- `text_boundary_policy=TextBoundaryPolicy.ANYWHERE`
- `text_backspace_policy=TextBackspacePolicy.EDIT_BUFFER`
- `os_key_repeat_policy=OsKeyRepeatPolicy.MATCH`
- `replacement_policy=ReplacementPolicy.MINIMAL_DIFF`

### Practical interpretation

#### `case_sensitive`
Controls whether `a` and `A` are treated as different logical matches.

#### `respect_caps_lock`
Controls whether `CapsLock` contributes to the logical result.
For alphabetic text matching, this is usually only relevant when `case_sensitive=True`.
If `case_sensitive=False`, `respect_caps_lock=False` is often redundant, although keeping it explicit can still make intent clearer.

#### `ignore_modifier_keys` / `ignore_toggle_keys`
Mainly relevant to `LogicalBind` sequence and chord matching.
These let helper keys such as modifiers or toggles avoid breaking a logical match.

#### `text_ignore_ctrl_combos` / `text_ignore_alt_combos` / `text_ignore_win_combos`
Mainly relevant to text-stream matching.
These let shortcut-style combinations be ignored while collecting text.

#### `text_clear_buffer_on_non_text`
Controls whether unrelated non-text keys clear the collected text buffer.

---

## 9) Text matching policies

### `TextBoundaryPolicy`

Boundary policy controls **where** a text match is allowed.

```python
from keybinds import LogicalConfig, TextBoundaryPolicy

cfg = LogicalConfig(text_boundary_policy=TextBoundaryPolicy.WHOLE_WORD)
```

Available values:

- `ANYWHERE`
- `WORD_START`
- `WORD_END`
- `WHOLE_WORD`

#### `ANYWHERE`
Matches anywhere inside the typed text stream.

Examples:

- `123brb` → replacement may fire
- `brb123` → replacement may fire

#### `WORD_START`
Requires a word boundary on the left.

#### `WORD_END`
Requires a word boundary on the right.
This usually means the replacement fires after a terminating separator is typed.

#### `WHOLE_WORD`
Requires boundaries on both sides.

Examples:

- ` brb ` → replacement may fire
- `123brb` → does not match
- `brb123` → does not match

---

### `TextBackspacePolicy`

Backspace policy controls how the text matcher updates its internal buffer.

```python
from keybinds import LogicalConfig, TextBackspacePolicy

cfg = LogicalConfig(text_backspace_policy=TextBackspacePolicy.CLEAR_WORD)
```

Available values:

- `EDIT_BUFFER`
- `IGNORE`
- `CLEAR_BUFFER`
- `CLEAR_WORD`

#### `EDIT_BUFFER`
Treat Backspace like a normal editor would: remove the last buffered character.
This is the normal default.

#### `IGNORE`
Ignore Backspace for matcher state.

#### `CLEAR_BUFFER`
Backspace clears the whole collected text buffer.

#### `CLEAR_WORD`
Backspace clears the current word-like suffix up to the nearest boundary.

---

### `OsKeyRepeatPolicy`

OS key-repeat policy controls what happens when the operating system emits repeated keydown events while a key is held.

```python
from keybinds import LogicalConfig, OsKeyRepeatPolicy

cfg = LogicalConfig(os_key_repeat_policy=OsKeyRepeatPolicy.MATCH)
```

Available values:

- `IGNORE`
- `MATCH`
- `RESET`

#### `IGNORE`
Ignore OS repeat events for logical text collection.

#### `MATCH`
Allow repeated keydown events to contribute to matching.
This is the normal default because repeated keydown events are part of real text entry.

#### `RESET`
Treat OS repeat as a reason to reset the matcher state.

---

## 10) Replacement behavior for abbreviations

Abbreviation replacement behavior is controlled by `ReplacementPolicy`.

```python
from keybinds import LogicalConfig, ReplacementPolicy

cfg = LogicalConfig(replacement_policy=ReplacementPolicy.MINIMAL_DIFF)
```

Available values:

- `REPLACE_ALL`
- `APPEND_SUFFIX`
- `MINIMAL_DIFF`

### `REPLACE_ALL`
Remove the matched text and insert the replacement text in full.

### `APPEND_SUFFIX`
If the typed text is already a prefix of the replacement, insert only the missing suffix.
Otherwise fall back to a full replacement.

Example:

- `def` → `define` inserts `ine`

### `MINIMAL_DIFF`
Use the smallest practical edit based on the matched text and replacement.
This is the current default.

Examples:

- `def` → `define` usually just inserts `ine`
- `omw` → `on my way` usually replaces the differing suffix instead of blindly erasing and retyping everything

---

## 11) Practical examples

### Case-insensitive text matching

```python
from keybinds import Hook, LogicalConfig

hook = Hook()

hook.bind_text(
    "Hello!",
    lambda: print("matched"),
    logical_config=LogicalConfig(case_sensitive=False),
)
```

### Ignore CapsLock while matching text

```python
from keybinds import Hook, LogicalConfig

hook = Hook()

hook.bind_text(
    "hello",
    callback,
    logical_config=LogicalConfig(
        case_sensitive=False,
        # Often redundant when case_sensitive=False, but explicit is fine.
        respect_caps_lock=False,
    ),
)
```

### Whole-word abbreviation

```python
from keybinds import Hook, LogicalConfig, TextBoundaryPolicy

hook = Hook()

hook.add_abbreviation(
    "brb",
    "be right back",
    logical_config=LogicalConfig(
        text_boundary_policy=TextBoundaryPolicy.WHOLE_WORD,
    ),
)
```

This is useful when you want:

- ` brb ` → ` be right back `
- but not `123brb` or `brb123`

### Different backspace behavior

```python
from keybinds import Hook, LogicalConfig, TextBackspacePolicy

hook = Hook()

hook.bind_text(
    "abc",
    callback,
    logical_config=LogicalConfig(
        text_backspace_policy=TextBackspacePolicy.CLEAR_BUFFER,
    ),
)
```

### Comma on any layout path that produces `,`

```python
hook.bind_logical(r"\,", lambda: print("comma"))
```

This is intended to match the logical comma character, not just one fixed physical key.

---

## 12) Decorator helpers

All logical decorator helpers use the default hook unless you pass `hook=` explicitly. Use `add_abbreviation(...)` as a regular helper function; use `bind_abbreviation(...)` as the decorator form.

```python
import keybinds
from keybinds import Hook, bind_logical, bind_text, add_abbreviation

custom = Hook()

@bind_logical("ctrl+A", hook=custom)
def on_shortcut():
    print("shortcut")

@bind_text("hello")
def on_hello():
    print("hello")

@bind_abbreviation("brb", "be right back")
def on_expand():
    print("expanded")

custom.join()
```

Use `add_abbreviation(...)` as a helper function that forwards to `get_default_hook().add_abbreviation(...)`. Use `bind_abbreviation(...)` as the decorator form; it behaves like `hook.add_abbreviation(...)`, but it also calls the decorated function after the replacement is applied.

## 13) Limitations and current status

Logical input support is **experimental**.

Current expectations:

- normal VK-based binds remain the most mature API
- logical binds are the right choice when layout-aware character matching matters
- text matching and abbreviation support aim to track the resulting text stream, not just physical keys

Current caveats:

- behavior can still vary across editors and applications
- dead keys and complex layout transitions may require further refinement
- IME-heavy environments are not yet a primary target
- some semantics may still evolve as the experimental API stabilizes

If you need the most predictable behavior for traditional shortcuts such as `ctrl+s`, prefer normal `hook.bind(...)`.
If you need character-aware or text-aware behavior, use the logical APIs and test in the real applications you care about.
