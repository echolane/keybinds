import asyncio
import keybinds
from keybinds.decorators import bind_key


@bind_key("f1")
async def fetch_data():
    print("Start async task...")

    # some async task
    await asyncio.sleep(1.5)

    print("Done!")


@bind_key("f2")
async def parallel_task():
    await asyncio.gather(
        asyncio.sleep(0.5),
        asyncio.sleep(0.5),
    )
    print("Parallel finished")


print("F1 to start async task, F2 to start parallel task.")
keybinds.join()
