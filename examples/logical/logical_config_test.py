from keybinds import Hook, LogicalConfig

hook = Hook(default_logical_config=LogicalConfig(
    case_sensitive=False,
    respect_caps_lock=False,
))

# Case-insensitive logical bind, CapsLock ignored.
hook.bind_logical("ctrl+A", lambda: print("MATCH: ctrl+A / ctrl+a"))
hook.bind_logical("A", lambda: print("MATCH: A or a"))

# Text abbreviations
hook.add_abbreviation("brb", "be right back")
hook.add_abbreviation(
    "Hello!",
    "Hi there!",
    logical_config=LogicalConfig(
        case_sensitive=False,
        respect_caps_lock=False,
        text_clear_buffer_on_non_text=True,
    ),
)

print("Running logical config test. Press Esc to exit.")
hook.start()
hook.join()
