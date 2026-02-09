from keybinds.bind import Hook

hook = Hook()
hook.bind("ctrl+e", lambda: print("CTRL+E"))
hook.bind_mouse("left", lambda: print("LEFT"))

hook.join()
