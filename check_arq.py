import inspect
from Python_ARQ import ARQ

print("========== ARQ LUNA SOURCE ==========")

try:
    print(inspect.getsource(ARQ.luna))
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
