import inspect
from Python_ARQ import ARQ

print("========== ARQ FETCH SOURCE ==========", flush=True)

try:
    print(inspect.getsource(ARQ._fetch), flush=True)
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}", flush=True)
