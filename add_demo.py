"""Run from repo root:  python add_demo.py   (copies nothing; just wires app/routers/demo.py into app/main.py)"""
from pathlib import Path
import sys
m = Path("app/main.py")
if not Path("app/routers/demo.py").exists():
    sys.exit("Copy demo.py into app\\routers\\ first.")
s = m.read_text(encoding="utf-8")
if "demo.router" in s:
    sys.exit("Already wired.")
a = "from app.routers import webhook\n"
b = 'app.include_router(webhook.router, prefix="/webhook", tags=["Webhook"])\n'
assert a in s and b in s, "main.py layout changed; paste me the router lines."
s = s.replace(a, "from app.routers import webhook, demo\n").replace(
    b, b + '\nif os.getenv("DEMO_MODE") == "1":\n    app.include_router(demo.router)\n')
m.write_text(s, encoding="utf-8"); print("Wired demo router into app/main.py")
