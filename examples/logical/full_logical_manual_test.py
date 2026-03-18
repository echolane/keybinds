from keybinds import Hook, LogicalConfig


def section(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72, flush=True)


def hit(name: str):
    def _cb():
        print(f"[HIT] {name}", flush=True)
    return _cb


section("Full logical/text manual test")
print("Open a text field (Notepad is ideal) and keep this console visible.")
print("The hook is already active once the script starts.")
print("Press Esc in the target app to stop only if your environment maps it that way; otherwise Ctrl+C in console.")
print(flush=True)

hook = Hook()

section("1) LogicalBind: single chars, punctuation, Ctrl+letter")
print("Try these and watch the console:")
print("  a")
print("  A")
print("  ,")
print("  +")
print("  !")
print("  Ctrl+A")
print("  Ctrl+a")
print(flush=True)

hook.bind_logical("a", hit("logical: a"))
hook.bind_logical("A", hit("logical: A"))
hook.bind_logical(r"\,", hit("logical: comma"))
hook.bind_logical(r"\+", hit("logical: plus"))
hook.bind_logical(r"\!", hit("logical: exclamation"))
hook.bind_logical("ctrl+A", hit("logical: ctrl+A"))
hook.bind_logical("ctrl+a", hit("logical: ctrl+a"))

section("2) LogicalBind: logical sequences")
print("These are sequence binds, not text-stream binds.")
print("Try typing exactly:")
print("  Hello!")
print("  @@")
print(flush=True)

hook.bind_logical("H,e,l,l,o,!", hit("logical-sequence: Hello!"), logical_config=LogicalConfig(case_sensitive=False))
hook.bind_logical("@,@", hit("logical-sequence: @@"))

section("3) bind_text: typed-text matching")
print("These should match the produced text, regardless of helper keys such as Shift/CapsLock.")
print("Try typing:")
print("  Hello!")
print("  hello!")
print("  BRB")
print("  brb")
print("  A!")
print(flush=True)

hook.bind_text(
    "Hello!",
    hit("text: Hello! (case-sensitive)"),
)

hook.bind_text(
    "Hello!",
    hit("text: Hello! (case-insensitive, ignore CapsLock)"),
    logical_config=LogicalConfig(case_sensitive=False),
)

hook.bind_text(
    "brb",
    hit("text: brb (case-insensitive, ignore CapsLock)"),
    logical_config=LogicalConfig(case_sensitive=False),
)

hook.bind_text(
    "A!",
    hit("text: A! (case-insensitive, ignore CapsLock)"),
    logical_config=LogicalConfig(case_sensitive=False),
)   

section("4) add_abbreviation: text expansion")
print("Try typing these in a text field:")
print("  @@    -> user@example.com")
print("  brb   -> be right back")
print("  omw   -> on my way")
print("  Hello! -> Hi there!")
print(flush=True)

hook.add_abbreviation("@@", "user@example.com")
hook.add_abbreviation(
    "brb",
    "be right back",
    logical_config=LogicalConfig(
        case_sensitive=False,
        respect_caps_lock=False,
        text_clear_buffer_on_non_text=False,
    ),
)
hook.add_abbreviation(
    "omw",
    "on my way",
    logical_config=LogicalConfig(
        case_sensitive=False,
        respect_caps_lock=False,
        text_clear_buffer_on_non_text=False,
    ),
)
hook.add_abbreviation(
    "Hello!",
    "Hi there!",
    logical_config=LogicalConfig(
        case_sensitive=False,
        respect_caps_lock=False,
        text_clear_buffer_on_non_text=False,
    ),
)

section("5) bind_text buffer-policy checks")
print("Two similar tests:")
print("  alpha  -> one bind keeps buffer across non-text keys")
print("  beta   -> one bind clears buffer on non-text keys")
print("Suggested check:")
print("  Type 'al', press Left/Right arrow or F1, then finish 'pha'")
print("  Type 'be', press Left/Right arrow or F1, then finish 'ta'")
print(flush=True)

hook.bind_text(
    "alpha",
    hit("text-policy: alpha (buffer survives non-text keys)"),
    logical_config=LogicalConfig(
        case_sensitive=False,
        respect_caps_lock=False,
        text_clear_buffer_on_non_text=False,
    ),
)

hook.bind_text(
    "beta",
    hit("text-policy: beta (buffer clears on non-text keys)"),
    logical_config=LogicalConfig(
        case_sensitive=False,
        respect_caps_lock=False,
        text_clear_buffer_on_non_text=True,
    ),
)

section("6) bind_text backspace behavior")
print("Try:")
print("  type 'abx', press Backspace, then type 'c'")
print("Expected: 'abc' matcher should still fire if backspace edits buffer.")
print(flush=True)

hook.bind_text(
    "abc",
    hit("text-policy: abc with backspace edit"),
    logical_config=LogicalConfig(
        case_sensitive=False,
        respect_caps_lock=False,
        text_backspace_edits_buffer=True,
    ),
)

section("Expected observations")
print("1. bind_logical for punctuation should match the final symbol, not the physical key.")
print("2. bind_text / add_abbreviation should be more reliable than sequence-based bind_logical for real text.")
print("3. case_sensitive=False should make 'brb', 'BRB', 'BrB' all match the same text bind.")
print("4. respect_caps_lock=False should stop CapsLock from changing the logical comparison result.")
print("5. text_clear_buffer_on_non_text=True should cause a non-text key to break the in-progress text match.")
print(flush=True)

print("\nHook running. Use Ctrl+C in this console to exit.", flush=True)
hook.join()
