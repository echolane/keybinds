import asyncio
from keybinds import Hook
from keybinds.decorators import bind_key

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

# `asyncio_loop` is optional:
# – If keybinds is the only loop, just use keybinds.join() (no Hook needed).
# – If an external loop exists, pass it to Hook(...) and don't call join() since it blocks.
hook = Hook(asyncio_loop=loop)

enabled = True
q: asyncio.Queue[str] = asyncio.Queue()
sem = asyncio.Semaphore(2)          # 2 parallel tasks at once
running: set[asyncio.Task] = set()  # active tasks (for cancel)


async def worker():
    while True:
        job = await q.get()
        async with sem:
            t = asyncio.create_task(do_job(job))
            running.add(t)
            try:
                await t
            finally:
                running.discard(t)


async def do_job(name: str):
    try:
        print("start:", name)
        for i in range(3):
            await asyncio.sleep(0.3)
            print(f"{name}: step {i+1}/3")
        print("done:", name)
    except asyncio.CancelledError:
        print("canceled:", name)


@bind_key("f8", hook=hook)
async def toggle():
    global enabled
    enabled = not enabled
    print("enabled =", enabled)


@bind_key("f1", hook=hook)
async def enqueue():
    if not enabled:
        print("disabled -> skip")
        return
    await q.put("heavy_task")
    print("queued heavy_task")


@bind_key("ctrl+f2", hook=hook)
async def cancel_all():
    for t in list(running):
        t.cancel()
    print("cancel requested:", len(running))


async def main():
    asyncio.create_task(worker())
    await asyncio.get_running_loop().run_in_executor(None, hook.join)


print("Press F8 to toggle, F1 to enqueue, Ctrl+F2 to cancel.")
loop.run_until_complete(main())
