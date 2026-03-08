# Diagnostics

`keybinds` can explain why a bind fired, why it did not fire, or why it never even reached the callback.

For most problems, the workflow is simple:

1. enable diagnostics on the `Hook`
2. reproduce the problem
3. call `hook.explain(...)`

You usually do not need raw traces.

---

## Contents

- [1) Quick start](#1-quick-start)
- [2) Diagnostics levels](#2-diagnostics-levels)
- [3) The main tool: `hook.explain(...)`](#3-the-main-tool-hookexplain)
- [4) How to read a report](#4-how-to-read-a-report)
- [5) Typical situations](#5-typical-situations)
- [6) Complex triggers without the complexity](#6-complex-triggers-without-the-complexity)
- [7) Checks and named checks](#7-checks-and-named-checks)
- [8) Recent attempts and raw records](#8-recent-attempts-and-raw-records)
- [9) Performance](#9-performance)
- [10) Scope](#10-scope)

---

## 1) Quick start

Diagnostics are off by default.

```python
from keybinds import Hook
from keybinds.diagnostics import DiagnosticsConfig

hook = Hook(
    diagnostics=DiagnosticsConfig(
        enabled=True,
        level="decisions",
        ring_size=2000,
    )
)
```

Reproduce the problem, then ask the hook to explain one bind:

```python
report = hook.explain("ctrl+s", last_ms=5000)
print(report.render_text())
```

That is the normal starting point.

---

## 2) Diagnostics levels

`DiagnosticsConfig.level` accepts four values:

- `"off"`
- `"errors"`
- `"decisions"`
- `"trace"`

```python
hook = Hook(
    diagnostics=DiagnosticsConfig(enabled=True, level="decisions")
)
```

### Which one should I use?

| Level | Use it for | Notes |
|---|---|---|
| `"off"` | no diagnostics | default behavior |
| `"errors"` | callback or async failures | narrow and quiet |
| `"decisions"` | almost all troubleshooting | recommended default |
| `"trace"` | low-level investigation | much noisier |

Start with `"decisions"` unless you know you need more.

---

## 3) The main tool: `hook.explain(...)`

### Basic form

```python
report = hook.explain("ctrl+s", last_ms=5000)
print(report.render_text())
```

For mouse binds, use `hook.explain_mouse(...)` instead of `hook.explain(...)`.
This avoids ambiguity with key names such as `"left"`, `"right"`, `"up"`, and `"down"`.

```python
report = hook.explain_mouse("left", last_ms=5000)
print(report.render_text())
```

### Selecting which recent attempt to explain

`explain()` supports typed selection modes via `ExplainSelect`.

```python
report = hook.explain("ctrl+a, f", select="best")
```

Allowed values:

- `"best"`
- `"last"`
- `"last_fired"`
- `"last_failed"`

What they mean:

- `best` picks the most useful recent attempt for that bind
- `last` picks the most recent one, even if it was incomplete
- `last_fired` picks the most recent attempt where the bind fired
- `last_failed` picks the most recent meaningful failure

For normal use, keep `select="best"`.

### Controlling report size

`render_text()` supports typed verbosity modes via `ExplainVerbosity`.

```python
print(report.render_text(verbosity="short"))
print(report.render_text(verbosity="normal"))
print(report.render_text(verbosity="detailed"))
```

Allowed values:

- `"short"`
- `"normal"`
- `"detailed"`

A good rule of thumb:

- use `short` when you want the answer in one glance
- use `normal` for day-to-day troubleshooting
- use `detailed` when another bind may have competed with this one

---

## 4) How to read a report

A report tries to answer four practical questions:

- did the bind matter here at all?
- where did evaluation stop?
- why did it stop there?
- did the callback stage ever begin?

A normal report looks like this:

```text
Bind: f8
Result: callback not fired
Stopped at: trigger
Primary reason: key was released before hold threshold elapsed

Details:
- Trigger: on_hold
- Required hold time: 800 ms
- Actual hold time: 310 ms
- Dispatch: not reached
```

### `Result`

Common values are:

- `callback completed`
- `callback failed`
- `callback not fired`
- `no meaningful attempts found`

### `Stopped at`

Common stages are:

- `scope`
- `checks`
- `constraints`
- `trigger`
- `dispatch`

This is important because it tells you which class of problem you are looking at.

- `scope`, `checks`, `constraints`, or `trigger` mean the bind never reached callback dispatch
- `dispatch` means the bind did match, and the later stage is what failed

### `no meaningful attempts found`

This means diagnostics did not find a recent attempt where that bind became a real candidate.
It is better than inventing a weak explanation.

```text
Bind: ctrl+s
Result: no meaningful attempts found
Primary reason: this bind was not meaningfully involved in the selected time window
```

---

## 5) Typical situations

These are the cases most users actually care about.

### The bind fired normally

```text
Bind: ctrl+s
Result: callback completed
Stopped at: dispatch
Primary reason: callback completed successfully
```

### The bind matched, but the callback failed

```text
Bind: ctrl+shift+s
Result: callback failed
Stopped at: dispatch
Primary reason: callback raised RuntimeError: Disk is read-only
```

### The bind was close, but never fully matched

```text
Bind: ctrl+s
Result: callback not fired
Stopped at: trigger
Primary reason: required keys were not all active at the same time
```

### The bind is still waiting for something

This usually happens with click, hold, repeat, double tap, or sequences.

```text
Bind: g
Result: callback not fired
Stopped at: trigger
Primary reason: waiting for the second tap within 300 ms
```

### A different bind won

In `detailed` mode, diagnostics can show nearby competing candidates.

```text
Bind: ctrl+shift+u
Result: callback not fired
Stopped at: checks
Primary reason: check failed: can_upload

Other relevant candidates:
- ctrl+u: fired successfully
```

---

## 6) Complex triggers without the complexity

Diagnostics use the same report shape for simple and complex binds.
The difference is in the reason and in a few small details.

### Press / release

For simple binds, diagnostics mainly answer:

- was the chord ever fully active?
- for release binds, did the expected release happen?

Examples:

```text
Bind: ctrl+s
Result: callback not fired
Stopped at: trigger
Primary reason: required keys were not all active at the same time
```

```text
Bind: ctrl+t
Result: callback not fired
Stopped at: trigger
Primary reason: bind was waiting for key release
```

### Click

Click reports are about whether the press/release cycle completed.

```text
Bind: k
Result: callback not fired
Stopped at: trigger
Primary reason: click was started but not completed
```

### Hold

Hold reports are most useful when they stay short and numerical.

```text
Bind: f8
Result: callback not fired
Stopped at: trigger
Primary reason: key was released before hold threshold elapsed

Details:
- Trigger: on_hold
- Required hold time: 800 ms
- Actual hold time: 310 ms
- Dispatch: not reached
```

### Repeat

Repeat reports usually answer one question: did repeating ever begin?

```text
Bind: f9
Result: callback not fired
Stopped at: trigger
Primary reason: key was released before repeat delay elapsed
```

If repeating did begin, the report may mention the repeat tick count.

### Double tap / double click

These reports are usually about timing or interruption.

```text
Bind: g
Result: callback not fired
Stopped at: trigger
Primary reason: second tap did not arrive in time
```

```text
Bind: left
Result: callback not fired
Stopped at: trigger
Primary reason: double click was interrupted by a different button
```

### Sequence

Sequence reports answer three concrete questions:

- did the sequence start?
- how far did it get?
- what stopped it?

```text
Bind: ctrl+a, f
Result: callback not fired
Stopped at: trigger
Primary reason: sequence started but was not completed

Details:
- Trigger: on_sequence
- Matched steps: 1/2
- Expected next step: f
- Dispatch: not reached
```

```text
Bind: ctrl+a, f
Result: callback not fired
Stopped at: trigger
Primary reason: sequence was reset by an unrelated key

Details:
- Trigger: on_sequence
- Matched steps: 1/2
- Interrupting key: q
- Dispatch: not reached
```

```text
Bind: ctrl+a, f
Result: callback completed
Stopped at: dispatch
Primary reason: sequence completed successfully
```

---

## 7) Checks and named checks

Checks are much more helpful when they have names.

```python
from keybinds import BindConfig
from keybinds.diagnostics import named_check

hook.bind(
    "ctrl+shift+u",
    upload_file,
    config=BindConfig(
        checks=[
            named_check("can_upload", lambda e, s: state.can_upload),
        ]
    ),
)
```

That lets diagnostics say this:

```text
Bind: ctrl+shift+u
Result: callback not fired
Stopped at: checks
Primary reason: check failed: can_upload
```

Without a name, diagnostics can still report a failed check, but the message will be less useful.

---

## 8) Recent attempts and raw records

These tools are available, but they are secondary.

### Recent attempts

```python
attempts = hook.get_recent_attempts(last_ms=5000)
```

Use this when you are comparing several recent attempts or debugging diagnostics behavior itself.
For most users, `explain(...)` is the better starting point.

### Raw records

```python
records = hook.get_recent_diagnostics(limit=100)
```

Use raw records only when you need the low-level stream.
For normal troubleshooting, start with `explain(...)`.

---

## 9) Performance

Diagnostics are designed to stay lightweight when disabled and practical when enabled.

A few good defaults:

- leave diagnostics off unless you need them
- use `"decisions"` for most troubleshooting
- avoid `"trace"` unless you really need raw input visibility
- treat raw records as a development tool, not the default workflow

In short:

- `errors` is narrow and cheap
- `decisions` is the recommended balance
- `trace` is intentionally noisier and heavier

---

## 10) Scope

Diagnostics are designed to explain why a bind fired or did not fire.

By default, they summarize the most relevant attempt in the selected time window rather than dumping every low-level event.

Use `explain()` for normal troubleshooting and `get_recent_attempts()` when you need a more debugging-oriented view.
