"""Manual checks for keyboard and mouse capture APIs.

Run this file on Windows with the project installed or available on PYTHONPATH.
Each menu option asks for input only before starting its capture session.
"""

import asyncio
import queue
import threading
from typing import Callable, Dict, Optional, Tuple, Union

from keybinds import (
    CaptureConfig,
    CapturedKey,
    ChordEndPolicy,
    Hook,
    InjectedPolicy,
    InterceptAction,
    InterceptConfig,
    TextBackspacePolicy,
    token_to_vk,
    vk_to_char,
    vk_to_token,
)


def show_converters() -> None:
    print("VK 0x52 token:", vk_to_token(0x52))
    print("Token 'ctrl' VK:", hex(token_to_vk("ctrl")))
    print("Shift+R character for the active layout:", vk_to_char(0x52, shift=True))


def capture_one_key(hook: Hook) -> None:
    print("Press a key within 10 seconds. Esc cancels; the captured key is suppressed.")
    event = hook.capture_key(timeout=10.0)
    print("Capture result:", event)
    if event is not None:
        print("Fields:", event.vk, event.scan_code, event.token, repr(event.char), event.action, event.injected)


def capture_one_chord(hook: Hook) -> None:
    policies = {
        "1": ChordEndPolicy.FIRST_NON_MODIFIER,
        "2": ChordEndPolicy.ALL_RELEASED,
        "3": ChordEndPolicy.FIRST_RELEASED,
    }
    print("Chord completion: 1 = first non-modifier, 2 = all released, 3 = first released")
    policy = policies.get(input("Choose policy [1]: ").strip() or "1", ChordEndPolicy.FIRST_NON_MODIFIER)
    side_specific = input("Show left/right modifier names? [y/N]: ").strip().lower() == "y"
    respect_caps = input("Respect Caps Lock when calculating characters? [Y/n]: ").strip().lower() != "n"
    injected = _choose_injected_policy()
    hwnd = _read_hwnd()
    print("Press a chord. Esc cancels.")
    result = hook.capture_chord(
        timeout=10.0,
        on_change=lambda chord: print("Current chord:", chord.physical_expr),
        config=CaptureConfig(
            end_policy=policy,
            side_specific_modifiers=side_specific,
            respect_caps_lock=respect_caps,
            injected=injected,
            hwnd=hwnd,
        ),
    )
    if result is None:
        print("Chord capture canceled or timed out.")
        return
    print("Physical expression:", result.physical_expr)
    print("Logical expression:", result.logical_expr)
    print("Tokens:", result.tokens)
    print("VKs:", sorted(result.vks))
    print("Modifiers:", result.modifiers)


def capture_one_mouse(hook: Hook) -> None:
    print("Click a mouse button or scroll within 10 seconds. Esc does not cancel mouse capture.")
    event = hook.capture_mouse(timeout=10.0)
    print("Mouse capture result:", event)
    if event is not None:
        print("Fields:", event.button, event.action, event.x, event.y, event.wheel_delta, event.injected)


def stream_keyboard(hook: Hook) -> None:
    print("Suppression: 1 = pass all, 2 = suppress all, 3 = suppress x only, 4 = callable filter for x.")
    suppression = input("Choose mode [1]: ").strip() or "1"
    suppress = {
        "1": False,
        "2": True,
        "3": {"x"},
        "4": lambda event: event.token == "x",
    }.get(suppression, False)
    include_repeats = input("Include OS key repeats? [y/N]: ").strip().lower() == "y"
    pause_binds = input("Pause regular binds during this stream? [Y/n]: ").strip().lower() != "n"
    config = CaptureConfig(include_repeats=include_repeats, pause_binds=pause_binds)
    print("Keyboard stream active. Press Esc to stop.")
    with hook.stream_keys(suppress=suppress, config=config) as stream:
        for event in stream:
            print("Event:", event.token, event.action, "char=", repr(event.char))
            print("Held:", stream.current_chord().physical_expr)
            print("Ctrl held:", stream.is_pressed("ctrl"))
            print("Ctrl or Shift held:", stream.any_pressed(("ctrl", "shift")))
            print("Pressed-key count:", len(stream.pressed_keys()))
            if event == "esc" and event.action == "press":
                break


def stream_mouse(hook: Hook) -> None:
    print("Mouse stream active. The first button or wheel event ends this check.")
    with hook.stream_mouse(suppress=False) as stream:
        try:
            event = stream.get(timeout=15.0)
        except queue.Empty:
            print("No mouse event received before timeout.")
            return
        print("Event:", event.button, event.action)
        print("Position:", event.x, event.y, "wheel delta:", event.wheel_delta)


def _print_intercept_events(events: queue.Queue, stop: threading.Event) -> None:
    while True:
        try:
            item = events.get(timeout=0.1)
        except queue.Empty:
            if stop.is_set():
                return
            continue
        if item is None:
            return
        event, decision = item
        print("Intercepted:", event, "decision:", decision)


def intercept_keyboard_and_mouse(hook: Hook) -> None:
    target_key = input("Key token to suppress (for example x), or leave blank: ").strip().lower()
    target_button = input("Mouse button to suppress (left/right/middle/x1/x2), or leave blank: ").strip().lower()
    hwnd = _read_hwnd()
    print("Interception active. Press Esc to stop. Decisions are resolved before event logging.")

    events: queue.Queue = queue.Queue()
    stop_printer: threading.Event = threading.Event()
    printer: threading.Thread = threading.Thread(
        target=_print_intercept_events,
        args=(events, stop_printer),
        daemon=True,
    )
    printer.start()

    try:
        with hook.intercept(
            keyboard=True,
            mouse=True,
            config=InterceptConfig(
                hook_timeout=0.08,
                default_action=InterceptAction.PASS,
                pause_binds=False,
                injected=InjectedPolicy.ALLOW,
                hwnd=hwnd,
            ),
        ) as stream:
            for event in stream:
                stop = isinstance(event, CapturedKey) and event == "esc" and event.action == "press"
                suppress = (
                    isinstance(event, CapturedKey)
                    and bool(target_key)
                    and event == target_key
                ) or (
                    not isinstance(event, CapturedKey)
                    and bool(target_button)
                    and event.button == target_button
                )

                if suppress:
                    event.suppress()
                else:
                    event.accept()

                # Logging happens on another thread so the hook callback returns quickly.
                events.put_nowait((event, "suppressed" if suppress else "accepted"))
                if stop:
                    break
    finally:
        events.put_nowait(None)
        printer.join(timeout=1.0)
        stop_printer.set()


def read_text(hook: Hook) -> None:
    print("Type text, press Enter to finish, or Esc to cancel. Input is suppressed.")
    text = hook.read_text(
        until="enter",
        cancel_key="esc",
        suppress=True,
        backspace_policy=TextBackspacePolicy.EDIT_BUFFER,
        timeout=30.0,
    )
    print("Text result:", repr(text))


def capture_async_key(hook: Hook) -> None:
    print("Press a key within 10 seconds. Esc cancels.")
    event = asyncio.run(hook.capture_key_async(timeout=10.0))
    print("Async capture result:", event)


def stream_async_keys(hook: Hook) -> None:
    print("Async keyboard stream active. Press Esc to stop.")

    async def consume() -> None:
        with hook.stream_keys(suppress=False) as stream:
            async for event in stream:
                print("Async event:", event.token, event.action)
                if event == "esc" and event.action == "press":
                    stream.stop()
                    break

    asyncio.run(consume())


def stream_text_preview(hook: Hook) -> None:
    print("Type text and press Enter to finish, or Esc to cancel.")
    config = CaptureConfig(include_repeats=True)
    with hook.stream_text(until="enter", cancel_key="esc", timeout=30.0, config=config) as stream:
        for current_text in stream:
            print("Current text:", repr(current_text))
    print("Final text:", repr(stream.text), "canceled:", stream.cancelled)


def _read_hwnd() -> Optional[Union[int, str]]:
    value = input("Target window title or HWND, or leave blank for any window: ").strip()
    if not value:
        return None
    if value.lower().startswith("0x"):
        return int(value, 16)
    if value.isdecimal():
        return int(value)
    return value


def _choose_injected_policy() -> InjectedPolicy:
    options = {
        "1": InjectedPolicy.IGNORE,
        "2": InjectedPolicy.ALLOW,
        "3": InjectedPolicy.ONLY,
    }
    print("Injected input: 1 = ignore, 2 = allow, 3 = only injected input.")
    return options.get(input("Choose policy [1]: ").strip() or "1", InjectedPolicy.IGNORE)


MENU: Dict[str, Tuple[str, Callable[..., None]]] = {
    "1": ("Converters", show_converters),
    "2": ("Capture one key", capture_one_key),
    "3": ("Capture a chord", capture_one_chord),
    "4": ("Capture one mouse event", capture_one_mouse),
    "5": ("Stream keyboard events", stream_keyboard),
    "6": ("Stream one mouse event", stream_mouse),
    "7": ("Intercept keyboard and mouse", intercept_keyboard_and_mouse),
    "8": ("Read text", read_text),
    "9": ("Async key capture", capture_async_key),
    "10": ("Async keyboard stream", stream_async_keys),
    "11": ("Stream text preview", stream_text_preview),
}


def main() -> None:
    print("keybinds input capture manual checks")
    with Hook() as hook:
        while True:
            print("\n".join(f"{number}. {label}" for number, (label, _) in MENU.items()))
            print("q. Quit")
            choice = input("Select a check: ").strip().lower()
            if choice == "q":
                break
            selected = MENU.get(choice)
            if selected is None:
                print("Unknown option.")
                continue
            label, check = selected
            print(f"\n--- {label} ---")
            try:
                if check is show_converters:
                    check()
                else:
                    check(hook)
            except KeyboardInterrupt:
                print("Check interrupted.")
            except Exception as exc:
                print(f"Check failed: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
