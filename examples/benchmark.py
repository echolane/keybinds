import time
import ctypes
from ctypes import wintypes

# ---------- timer 1ms ----------
winmm = ctypes.WinDLL("winmm", use_last_error=True)
winmm.timeBeginPeriod.argtypes = [wintypes.UINT]
winmm.timeBeginPeriod.restype = wintypes.UINT
winmm.timeEndPeriod.argtypes = [wintypes.UINT]
winmm.timeEndPeriod.restype = wintypes.UINT

def timer_1ms(enable: bool) -> None:
    fn = winmm.timeBeginPeriod if enable else winmm.timeEndPeriod
    res = fn(1)
    # 0 = TIMERR_NOERROR
    if res != 0:
        raise OSError(f"{fn.__name__}(1) failed: {res}")

# ---------- SendInput ----------
user32 = ctypes.WinDLL("user32", use_last_error=True)

ULONG_PTR = ctypes.c_size_t
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002

VK_F8 = 0x77

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]

class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]

class INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("ki", KEYBDINPUT),
        ("mi", MOUSEINPUT),
        ("hi", HARDWAREINPUT),
    ]

class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [
        ("type", wintypes.DWORD),
        ("u", INPUT_UNION),
    ]

user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
user32.SendInput.restype = wintypes.UINT

def send_key_tap(vk: int) -> None:
    arr = (INPUT * 2)()

    arr[0].type = INPUT_KEYBOARD
    arr[0].ki = KEYBDINPUT(vk, 0, 0, 0, ULONG_PTR(0))

    arr[1].type = INPUT_KEYBOARD
    arr[1].ki = KEYBDINPUT(vk, 0, KEYEVENTF_KEYUP, 0, ULONG_PTR(0))

    sent = user32.SendInput(2, ctypes.cast(arr, ctypes.POINTER(INPUT)), ctypes.sizeof(INPUT))
    if sent != 2:
        raise ctypes.WinError(ctypes.get_last_error())

# ---------- stats ----------
def pct(values, p: float) -> float:
    if not values:
        return float("nan")
    s = sorted(values)
    k = int(round((len(s) - 1) * p))
    return s[k]

def summarize_ns(lat_ns: list[int]) -> dict:
    return {
        "count": len(lat_ns),
        "p50_ms": pct(lat_ns, 0.50) / 1e6,
        "p90_ms": pct(lat_ns, 0.90) / 1e6,
        "p99_ms": pct(lat_ns, 0.99) / 1e6,
        "max_ms": (max(lat_ns) / 1e6) if lat_ns else float("nan"),
    }

# ---------- benchmark ----------
def run(use_1ms: bool, n_events: int = 10000, warmup: int = 1000):
    from keybinds.bind import Hook
    from keybinds.types import BindConfig, Trigger, InjectedPolicy

    hook = Hook()
    cb_times = []

    def cb(*args, **kwargs):
        cb_times.append(time.perf_counter_ns())

    hook.bind("f8", cb, config=BindConfig(trigger=Trigger.ON_PRESS, injected=InjectedPolicy.ALLOW))

    if use_1ms:
        timer_1ms(True)

    try:
        time.sleep(0.1)

        for _ in range(warmup):
            send_key_tap(VK_F8)
        time.sleep(0.05)
        cb_times.clear()

        send_times = []
        for _ in range(n_events):
            send_times.append(time.perf_counter_ns())
            send_key_tap(VK_F8)

        deadline = time.time() + 10.0
        while len(cb_times) < n_events and time.time() < deadline:
            time.sleep(0.001)

        m = min(len(send_times), len(cb_times))
        lat_ns = [cb_times[i] - send_times[i] for i in range(m)]

        print("\n===", "WITH 1ms timer" if use_1ms else "BASELINE", "===")
        print("received:", len(cb_times), "/", n_events, "| used:", m)
        print(summarize_ns(lat_ns))

    finally:
        if use_1ms:
            try:
                timer_1ms(False)
            except Exception:
                pass

        hook.stop()

def main():
    print('Starting benchmark, press "CTRL+C" to stop.')
    run(False)
    run(True)

if __name__ == "__main__":
 for _ in range(3):
    main()
