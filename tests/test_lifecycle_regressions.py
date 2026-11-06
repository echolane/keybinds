from __future__ import annotations

import threading


def test_dispatcher_restart_uses_fresh_worker_queue(runtime_env):
    dispatcher_module = runtime_env.loader.load(
        'keybinds._dispatcher_regression', 'keybinds/_dispatcher.py'
    )
    dispatcher = dispatcher_module._CallbackDispatcher(workers=1)
    try:
        for _ in range(20):
            dispatcher.stop()
            dispatcher.start()
            completed = threading.Event()
            dispatcher.submit(completed.set)
            assert completed.wait(1)
    finally:
        dispatcher.stop()


def test_close_stops_dispatcher_when_hook_never_started(runtime_env):
    hook = runtime_env.make_hook()
    workers = list(hook._dispatcher._threads)

    hook.close()

    for worker in workers:
        worker.join(1)
        assert not worker.is_alive()


def test_start_after_stop_and_close_clears_wait_signal(runtime_env):
    hook = runtime_env.make_hook()
    hook.start()
    hook.stop()
    assert hook.wait(0)

    hook.close()
    hook.start()

    assert not hook.wait(0)
    hook.close()
