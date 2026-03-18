from keybinds import (
    Hook,
    LogicalConfig,
    TextBackspacePolicy,
    OsKeyRepeatPolicy,
)

hook = Hook()

hook.bind_text(
    "abc",
    lambda: print("MATCH: abc [EDIT_BUFFER]"),
    logical_config=LogicalConfig(
        text_backspace_policy=TextBackspacePolicy.EDIT_BUFFER,
        os_key_repeat_policy=OsKeyRepeatPolicy.IGNORE,
    ),
)

hook.bind_text(
    "def",
    lambda: print("MATCH: def [CLEAR_BUFFER]"),
    logical_config=LogicalConfig(
        text_backspace_policy=TextBackspacePolicy.CLEAR_BUFFER,
        os_key_repeat_policy=OsKeyRepeatPolicy.IGNORE,
    ),
)

hook.bind_text(
    "ghi",
    lambda: print("MATCH: ghi [CLEAR_WORD]"),
    logical_config=LogicalConfig(
        text_backspace_policy=TextBackspacePolicy.CLEAR_WORD,
        os_key_repeat_policy=OsKeyRepeatPolicy.IGNORE,
    ),
)

hook.bind_text(
    "aaa",
    lambda: print("MATCH: aaa [REPEAT MATCH]"),
    logical_config=LogicalConfig(
        os_key_repeat_policy=OsKeyRepeatPolicy.MATCH,
    ),
)

hook.bind_logical(
    "a,a,a",
    lambda: print("MATCH: a,a,a [LOGICAL REPEAT MATCH]"),
    logical_config=LogicalConfig(
        os_key_repeat_policy=OsKeyRepeatPolicy.MATCH,
    ),
)

print("Backspace/repeat policy checks")
print("1) EDIT_BUFFER: type ab, press Backspace, then finish abc")
print("2) CLEAR_BUFFER: type de, press Backspace, then finish def")
print("3) CLEAR_WORD: type hello ghi, press Backspace, then finish ghi")
print("4) REPEAT MATCH text: hold the 'a' key until aaa is produced")
print("5) REPEAT MATCH logical: hold the 'a' key for a,a,a")
print("Esc to exit")

hook.start()
hook.join()
