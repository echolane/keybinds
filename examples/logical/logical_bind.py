from keybinds import Hook, LogicalConfig

hook = Hook(default_logical_config=LogicalConfig(case_sensitive=False, respect_caps_lock=False))

hook.bind_logical("ctrl+A", lambda: print("MATCH: ctrl+A"))
hook.bind_text("Hello!", lambda: print("MATCH: Hello!"))

hook.add_abbreviation("brb", "be right back")
hook.add_abbreviation("omw", "on my way")
hook.add_abbreviation("Hello!", "Hi there!", logical_config=LogicalConfig(case_sensitive=False, respect_caps_lock=False))

print("Logical bind / abbreviation demo running. Press Esc to exit.")
hook.start()
hook.join()
