# Input Capture, Streams, and Interception

Use this API to capture key presses, observe input, intercept events, or collect typed text.

The API is available on `Hook` and through module-level functions that use the default hook.

```python
from keybinds import Hook

hook = Hook()
```

These features use Windows low-level hooks. Keep the `Hook` open while using them.
Stream context managers start and stop their sessions automatically.

For a hands-on walkthrough, run [`examples/capture_manual.py`](./examples/capture_manual.py) on Windows.

## Quick Start

### Capture a key or chord

```python
key = hook.capture_key(timeout=5)
if key is not None:
    print(key.token, key.char)

chord = hook.capture_chord(timeout=5)
if chord:
    print(chord.physical_expr)  # Physical form, for example: ctrl+shift+r
    print(chord.logical_expr)   # Character form for the current layout
    print(chord.tokens)         # Tokens in the chord
```

Capture methods return `None` if canceled with `esc` or if they time out.
Async variants are available, for example:

```python
key = await hook.capture_key_async(timeout=5)
```

### Observe keys without pausing regular binds

```python
with hook.stream_keys() as stream:
    for event in stream:
        print(event.token, event.action)
        if event == "esc":
            break
```

Keyboard and mouse streams leave regular binds active by default.
They also support `async with` and `async for`:

```python
async with hook.stream_keys() as stream:
    async for event in stream:
        print(event.token, event.action)
        if event == "esc":
            break
```

Mouse streams yield `CapturedMouse` events:

```python
with hook.stream_mouse() as stream:
    for event in stream:
        if event.action == "press":
            print("Button pressed:", event.button, "at", event.x, event.y)
        elif event.action == "scroll":
            print("Wheel delta:", event.wheel_delta)
```

### Decide whether an event reaches Windows

Interception waits for your decision. Resolve each event promptly.

Async iteration waits for input without blocking the event loop. Long synchronous work in the loop body still blocks it.

```python
async with hook.intercept() as stream:
    async for event in stream:
        if event == "r" and stream.is_pressed("ctrl"):
            event.suppress()
        else:
            event.accept()
```

Resolve each event with one of these methods:

- `event.accept()` passes it through to Windows.
- `event.suppress()` blocks it.

If you leave an event unresolved, it is accepted when iteration advances or when the context exits. If `hook_timeout` expires first, `default_action` is used.

### Read typed text

```python
text = hook.read_text(until="enter", cancel_key="esc", timeout=10)
if text is not None:
    print(text)
```

For live previews, use `stream_text`:

```python
with hook.stream_text(until="enter") as stream:
    for current_text in stream:
        render_search_preview(current_text)

print("Final text:", stream.text)
```

## Common Options

### Suppressing input

Defaults depend on the operation:

- One-shot capture suppresses events.
- Keyboard and mouse streams pass events through.

Set `suppress=True` to suppress all captured events. You can also pass tokens or button names to select events, or a callable that decides for each event.

### Pausing regular binds

By default, one-shot capture and text input pause regular binds. Keyboard and mouse streams do not.

- Set `CaptureConfig(pause_binds=True)` to pause binds during a stream.
- Set `CaptureConfig(pause_binds=False)` to keep binds active during text input.

```python
from keybinds import CaptureConfig

with hook.stream_keys(config=CaptureConfig(pause_binds=True)) as stream:
    for event in stream:
        ...
```

### Key repeat

Capture and text streams ignore OS key repeats by default. Enable them with `CaptureConfig(include_repeats=True)`.

Interception always reports repeats as `event.action == "repeat"`:

```python
with hook.intercept() as stream:
    for event in stream:
        if event.action == "repeat":
            event.suppress()
        else:
            event.accept()
```

## API Reference

The sections below describe event models, configuration fields, and conversion helpers.

### Event Models

`CapturedKey` has these fields:

| Field | Meaning |
| --- | --- |
| `vk` | Virtual key code |
| `scan_code` | Hardware scan code |
| `token` | Physical key token, such as `"r"` or `"ctrl"` |
| `char` | Printable character for the active layout, or `None` |
| `action` | `"press"`, `"release"`, or `"repeat"` |
| `is_modifier` | Whether the key is a modifier |
| `injected` | Whether the event came from injected input |
| `timestamp` | Monotonic event time |

`CapturedKey.is_printable` is true when `char` is not `None`.
Keys can be compared with a token, character, or virtual key code:

```python
if event == "r":
    ...
```

`CapturedChord` contains keys in press order. Use `physical_expr` with `bind()`.
`logical_expr` represents characters produced by the current layout.
The model also exposes `tokens`, `vks`, and `modifiers`.

`CapturedMouse` contains the button, action, position, wheel delta, injection flag, and timestamp.
Button names include `left`, `right`, `middle`, `x1`, `x2`, `wheel_up`, and `wheel_down`.

### CaptureConfig

`CaptureConfig` applies to one-shot capture, keyboard and mouse streams, and text input.
The table lists each option and its default.

| Field | Default | Meaning |
| --- | --- | --- |
| `end_policy` | `FIRST_NON_MODIFIER` | When chord capture ends: on the first regular key, first release, or after all keys are released |
| `side_specific_modifiers` | `False` | Distinguish left and right modifier tokens |
| `cancel_key` | `"esc"` | Key that cancels one-shot capture or text input; use `None` to disable |
| `pause_binds` | `True` | Pause regular binds during one-shot capture and text input; streams override this to `False` by default |
| `ignore_already_pressed` | `True` | Ignore keys or mouse buttons held when the session starts |
| `include_repeats` | `False` | Include OS repeat events in capture and text streams |
| `respect_caps_lock` | `True` | Apply Caps Lock when calculating `char` |
| `injected` | `InjectedPolicy.IGNORE` | Which physical or injected events to accept |
| `hwnd` | `None` | Accept events only while an HWND or exact window title is focused |

Choose a chord end policy from `FIRST_NON_MODIFIER`, `FIRST_RELEASED`, or `ALL_RELEASED`.

### InterceptConfig

| Field | Default | Meaning |
| --- | --- | --- |
| `hook_timeout` | `0.08` | Maximum time the low-level hook waits for a decision |
| `default_action` | `InterceptAction.PASS` | Action used when the decision times out |
| `pause_binds` | `False` | Pause regular binds for the interception session |
| `injected` | `InjectedPolicy.ALLOW` | Which physical or injected events to intercept |
| `respect_caps_lock` | `True` | Apply Caps Lock when calculating `char` |
| `hwnd` | `None` | Intercept events only while an HWND or exact window title is focused |

`InterceptAction.PASS` lets an event reach Windows. `InterceptAction.SUPPRESS` blocks it.
Resolve events before starting slow work; move that work to a worker thread or another task.

### Text Backspace Policies

Pass a `TextBackspacePolicy` to `read_text` or `stream_text`:

| Policy | Behavior |
| --- | --- |
| `EDIT_BUFFER` | Remove the previous character |
| `IGNORE` | Leave the text unchanged |
| `CLEAR_BUFFER` | Clear all collected text |
| `CLEAR_WORD` | Remove the previous word |

Text input uses `CaptureConfig()` defaults, including pausing regular binds.

- Keep binds active with `config=CaptureConfig(pause_binds=False)`.
- Include held-key repeats with `config=CaptureConfig(include_repeats=True)`.

### Key Converters

```python
from keybinds import vk_to_token, token_to_vk, vk_to_char

vk_to_token(0x52)                    # "r"
token_to_vk("ctrl")                 # VK_CONTROL
vk_to_char(0x52, shift=True)         # Active keyboard layout
vk_to_char(0x52, hwnd=target_hwnd)   # Target window's keyboard layout
```

`vk_to_char` returns `None` when the key has no printable character.
Its optional `hwnd` argument accepts a window handle or exact window title.

All models and configuration types are also available from `keybinds.capture`.
