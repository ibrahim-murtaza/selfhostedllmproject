import time
import requests

start = time.monotonic()
try:
    requests.get("http://127.0.0.1:11434/api/ps", timeout=10)
    print("Success")
except Exception as e:
    print(type(e).__name__, str(e))
print(f"Elapsed: {time.monotonic() - start:.2f}s")
