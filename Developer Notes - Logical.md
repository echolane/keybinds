# Developer Notes - Logical

This document explains the internal structure of the experimental logical-input layer.
It is aimed at contributors who need to read or modify the code, not at end users.

> **Experimental:** the logical-input API and internals are not yet stable. Code structure, state fields, and matching details may change between releases.

If you only need the public API, see **[Logical Binds and Abbreviations.md](./Logical%20Binds%20and%20Abbreviations.md)**.

---

## Contents

- [1) Files and responsibilities](#1-files-and-responsibilities)
- [2) Runtime model](#2-runtime-model)
- [3) `LogicalBind` at a glance](#3-logicalbind-at-a-glance)
- [4) Event pipeline in `logical/keyboard.py`](#4-event-pipeline-in-logicalkeyboardpy)
- [5) Why `pressed_chars` is rebuilt on each event](#5-why-pressed_chars-is-rebuilt-on-each-event)
- [6) The char-only sequence path](#6-the-char-only-sequence-path)
- [7) `TextAbbreviationBind` at a glance](#7-textabbreviationbind-at-a-glance)
- [8) Layout, modifiers, and translation](#8-layout-modifiers-and-translation)
- [9) Strict order internals](#9-strict-order-internals)
- [10) Common debugging questions](#10-common-debugging-questions)

---

## 1) Files and responsibilities

### `keybinds/logical/parsing.py`

Parses logical expressions into internal specs used at runtime.

Main pieces:
- `_LogicalVkGroup` — a group matched by VK membership
- `_LogicalCharGroup` — a group matched by a logical character
- `_LogicalChordSpec` — one chord step in a logical expression
- `parse_logical_expr(...)` — parses `ctrl+A`, `\,`, `a,b,c`, and mixed expressions
- `text_to_logical_expr(...)` — convenience helper for turning raw text into a logical sequence expression

### `keybinds/logical/translate.py`

Translates `vk + scanCode + flags + layout + modifiers` into a logical character.

Main pieces:
- `LogicalTranslator.current_layout()` — returns a safe current layout value, with fallback to the last known valid layout
- `LogicalTranslator.to_char(...)` — wraps `ToUnicodeEx`
- `LogicalTranslator.capslock_on()` — reads current CapsLock state

### `keybinds/logical/keyboard.py`

Implements `LogicalBind`, the matcher used by `Hook.bind_logical(...)`.

This module is responsible for:
- rebuilding logical characters for the current pressed-state
- matching logical chords and mixed sequences
- handling the char-only fast path for expressions like `a,b,c`
- integrating with the normal bind framework (`BaseBind`, triggers, suppression, diagnostics)

### `keybinds/logical/abbreviation.py`

Implements `TextAbbreviationBind`, which powers:
- `Hook.bind_text(...)`
- `Hook.add_abbreviation(...)`

This module is the text-stream matcher. It tracks *typed text history*, not chord state.

---

## 2) Runtime model

The logical-input layer uses two different runtime models.

### `LogicalBind`

`LogicalBind` is for logical key expressions.
It reasons about:
- the current hook event
- the current set of pressed VKs
- the current layout/modifier state
- the currently active step in a parsed logical sequence

This is the right model for expressions like:

```python
hook.bind_logical("ctrl+A", callback)
hook.bind_logical(r"\,", callback)
hook.bind_logical("ctrl+A,shift+B", callback)
```

### `TextAbbreviationBind`

`TextAbbreviationBind` is for typed text.
It reasons about:
- a rolling buffer of produced characters
- optional word-boundary rules
- replacement behavior
- editing operations such as Backspace

This is the right model for:

```python
hook.bind_text("hello", callback)
hook.add_abbreviation("brb", "be right back")
```

Do not treat these as interchangeable. They share translation helpers and config types, but they match different kinds of input state.

---

## 3) `LogicalBind` at a glance

Important fields in `LogicalBind`:

- `self.steps`
  Parsed logical expression as a tuple of `_LogicalChordSpec`

- `self.is_sequence`
  Whether the expression contains multiple comma-separated steps

- `self._translator`
  Shared VK/layout -> char translator

- `self._caps_on`
  Locally tracked CapsLock toggle state used during translation

- `self._seq_index`
  Current step index for mixed sequences

- `self._strict_order`
  Internal state object used only when `OrderPolicy` is strict

- `self._text_sequence`
  Cached tuple of characters for the special case where *every* step is exactly one `_LogicalCharGroup`

- `self._text_sequence_buffer`
  Rolling buffer for the char-only fast path

The important distinction is:
- `self._seq_index` is for the normal chord/sequence engine
- `self._text_sequence_buffer` is only for the char-only fast path

---

## 4) Event pipeline in `logical/keyboard.py`

The main entry point is `LogicalBind.handle(event, state)`.

The code path is intentionally ordered like this:

1. window/predicate checks
2. debounce and sequence timeout checks
3. injected-input filtering
4. char-only sequence fast path (`_handle_text_sequence`)
5. event-local translation context
6. current chord match
7. trigger/suppression handling

### Step 4: char-only sequence fast path

If the parsed expression looks like `a,b,c`, `LogicalBind` does **not** run the full mixed chord engine.
Instead it uses `_handle_text_sequence(...)`, which behaves more like a lightweight text matcher.

This path exists because pure character sequences are much more naturally matched by produced characters than by chord-state transitions.

### Step 5: event-local translation context

The following values are reconstructed on every event:
- `pressed_vks`
- modifier state (`shift`, `ctrl`, `alt`, `altgr`)
- active layout
- `event_char`
- `pressed_chars`

That data is then used for chord/sequence matching.

---

## 5) Why `pressed_chars` is rebuilt on each event

This is one of the most important implementation details.

It is tempting to cache:

```python
vk -> char
```

for pressed keys and reuse it later.
That turns out to be unreliable because the resulting character depends on:
- active layout
- Shift
- AltGr
- CapsLock
- the current event's real `scanCode` / `flags`

Because of that, `LogicalBind` uses `_compute_pressed_chars_snapshot(...)` to rebuild logical characters from the current pressed-state on every event.

The current event gets the real `scanCode` / `flags` from `winput.KeyboardEvent`.
Other already-pressed keys use translator fallback logic.

This is slower than a naive global cache, but much more predictable.

---

## 6) The char-only sequence path

`parse_logical_expr("a,b,c")` still produces normal parsed steps.
During initialization, `LogicalBind._build_text_sequence()` detects the special case where:
- the bind is a sequence
- every step has exactly one group
- every group is `_LogicalCharGroup`

If that is true, `_handle_text_sequence(...)` is enabled.

This path:
- ignores helper keys according to `LogicalConfig`
- translates each fresh keydown into a produced character
- appends that character to `self._text_sequence_buffer`
- compares the normalized rolling buffer against the normalized target tuple

This makes `a,b,c` behave more like a logical typed-character sequence than a strict progression of chord snapshots.

### Important limitation: `CLEAR_WORD` vs `CLEAR_BUFFER`

For the char-only sequence path, `LogicalBind` does **not** keep a full text stream.
`self._text_sequence_buffer` only stores the short rolling suffix needed to compare against the target sequence.

That means this path does not know enough context to reliably answer questions such as:
- where the current word started
- whether an earlier character was a word boundary
- how much text existed before the current matcher window

Because of that, `TextBackspacePolicy.CLEAR_WORD` cannot have a truly separate meaning here unless the matcher is redesigned to keep a larger text buffer.
In practice, this path should treat `CLEAR_WORD` the same as `CLEAR_BUFFER`.

This limitation applies to `LogicalBind` char-only sequences such as `a,b,c`.
It does **not** apply to `TextAbbreviationBind`, which tracks a real rolling text buffer and can reason about word boundaries.

---

## 7) `TextAbbreviationBind` at a glance

Important fields in `TextAbbreviationBind`:

- `self.typed`
  Raw typed suffix to match

- `self._typed_norm`
  Pre-normalized target text used for comparisons

- `self._buffer`
  Rolling text buffer of produced characters

- `self.last_match`
  Most recent match object, mostly useful for inspection

- `self._pending_matches`
  Queue of matches waiting to be consumed by the callback path

- `self._pending_fire_vk`
  The VK whose key-up should trigger the actual replacement callback

The most important design point: matching happens on key-down, but the replacement callback is delayed until the matching key's key-up. That avoids racing the target application's own text insertion.

---

## 8) Layout, modifiers, and translation

Both logical matchers share the same translator model.

The final character depends on:
- `vk`
- `scanCode`
- `flags`
- active layout
- modifier state
- effective CapsLock state

### Why `ctrl+letter` is special

For logical shortcuts such as `ctrl+A`, the library still tries to resolve the logical character even though `Ctrl` is pressed. This can be tricky because many keyboard APIs naturally drift toward control characters in that situation.

When debugging these cases, inspect:
- whether the current event has the expected `scanCode`
- whether the active layout is what you think it is
- whether `AltGr` is being inferred from `RightAlt + Ctrl`

### Layout fallback

`LogicalTranslator.current_layout()` keeps the last known valid layout.
If `GetKeyboardLayout(...)` briefly returns `NULL`, the translator reuses the last valid layout instead of failing the whole bind.

---

## 9) Strict order internals

`_LogicalStrictOrderState` is used only when `OrderPolicy` is:
- `STRICT`
- `STRICT_RECOVERABLE`

Its job is to answer a narrower question than `_match_chord(...)`:
- *given the currently pressed groups and the order in which events arrived, is this still a valid strict-order attempt?*

Important fields:
- `seen_groups` / `seen_set` — groups observed so far while building the chord
- `locked_prefix_len` — once the chord first becomes full, this freezes the prefix that must remain valid during release transitions
- `attempt_invalid` — only used in recoverable mode
- `invalid` — permanently invalidates the attempt

If you are debugging strict-order behavior, read these methods in order:
- `group_index_for_event(...)`
- `pressed_group_indices(...)`
- `on_event(...)`
- `allows_full(...)`
- `on_full_rising_edge(...)`

---

## 10) Common debugging questions

### “Why did `bind_logical("hello")` not behave like typed text?”

Because `bind_logical(...)` is still a logical key-expression matcher.
For typed text, use `bind_text(...)`.

### “Why does punctuation work but a word sequence does not?”

Check whether you really want:
- a logical key sequence (`bind_logical(...)`)
- or a text-stream match (`bind_text(...)`)

If the expression is pure characters separated by commas, `LogicalBind` will try to use the char-only path. Mixed expressions still use chord/sequence logic.

### “Where should I start reading when a logical bind fails?”

Read these in order:
1. `logical/parsing.py` — was the expression parsed the way you expect?
2. `logical/translate.py` — is the event translated into the expected character?
3. `LogicalBind.handle()` — does the bind take the text-sequence path or the mixed chord path?
4. `_match_chord(...)` — is the current chord considered full?
5. `_hook.py` / `_backend.py` — is the bind receiving the events you expect?

### “Why does the code sometimes look duplicated between `LogicalBind` and `TextAbbreviationBind`?”

Because they share translation concepts but solve different problems. A large part of the apparent duplication is intentional divergence between:
- chord/sequence state
- rolling text-buffer state

---

## See also

- **[Logical Binds and Abbreviations.md](./Logical%20Binds%20and%20Abbreviations.md)**
- **[Advanced Usage.md](./Advanced%20Usage.md)**
- **[Diagnostics.md](./Diagnostics.md)**
