from keybinds import Hook, LogicalConfig, TextBoundaryPolicy

hook = Hook()

hook.add_abbreviation(
    "def",
    "definitely",
    logical_config=LogicalConfig(text_boundary_policy=TextBoundaryPolicy.ANYWHERE),
)

hook.add_abbreviation(
    "asap",
    "as soon as possible",
    logical_config=LogicalConfig(text_boundary_policy=TextBoundaryPolicy.WORD_START),
)

hook.add_abbreviation(
    "lol",
    "laugh",
    logical_config=LogicalConfig(text_boundary_policy=TextBoundaryPolicy.WORD_END),
)

hook.add_abbreviation(
    "ok",
    "alright",
    logical_config=LogicalConfig(text_boundary_policy=TextBoundaryPolicy.WHOLE_WORD),
)

print("Checks:")
print("  ANYWHERE: 123def -> 123definitely ; def123 -> definitely123")
print("  WORD_START: ' asap' -> ' as soon as possible' ; '123asap' should not match")
print("  WORD_END: 'xlol ' -> 'xlaugh ' ; 'lol123' should not match")
print("  WHOLE_WORD: ' ok ' -> ' alright ' ; '123ok' and 'ok123' should not match")
print("Esc to exit")

hook.start()
hook.join()
