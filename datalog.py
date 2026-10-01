"""CSV logovanie meraní a záznam udalostí."""
import collections
import csv
import os
import re
import threading
import time
from datetime import datetime


def safe_name(name):
    name = re.sub(r"[^A-Za-z0-9_.-]+", "_", name.strip())[:80]
    return name.strip("._") or "log"


class DataLogger:
    FIELDS = ["time", "iso", "elapsed", "vset", "iset", "vout", "iout", "power", "mode", "output"]

    def __init__(self, folder, broker):
        self.folder = folder
        self.broker = broker
        self.lock = threading.Lock()
        self.file = None
        self.writer = None
        self.name = None
        self.interval = 1.0
        self.started = None
        self.last = 0.0
        self.rows = 0
        os.makedirs(folder, exist_ok=True)

    @property
    def active(self):
        return self.file is not None

    def info(self):
        return {
            "active": self.active,
            "name": self.name,
            "interval": self.interval,
            "started": self.started,
            "rows": self.rows,
        }

    def start(self, name, interval=1.0):
        with self.lock:
            self._stop()
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.name = f"{stamp}_{safe_name(name or 'log')}.csv"
            self.interval = max(0.2, float(interval))
            path = os.path.join(self.folder, self.name)
            self.file = open(path, "w", newline="")
            self.writer = csv.DictWriter(self.file, fieldnames=self.FIELDS)
            self.writer.writeheader()
            self.file.flush()
            self.started = time.time()
            self.last = 0.0
            self.rows = 0
        self.broker.publish("logger", self.info())
        return self.name

    def _stop(self):
        if self.file:
            try:
                self.file.close()
            except Exception:  # noqa: BLE001
                pass
        self.file = None
        self.writer = None

    def stop(self):
        with self.lock:
            was = self.name
            self._stop()
        self.broker.publish("logger", self.info())
        return was

    def tick(self, state):
        if not self.active:
            return
        now = time.time()
        if now - self.last < self.interval:
            return
        with self.lock:
            if not self.active:
                return
            self.last = now
            self.writer.writerow({
                "time": f"{now:.3f}",
                "iso": datetime.fromtimestamp(now).isoformat(timespec="milliseconds"),
                "elapsed": f"{now - self.started:.3f}",
                "vset": state.get("vset"),
                "iset": state.get("iset"),
                "vout": state.get("vout"),
                "iout": state.get("iout"),
                "power": state.get("power"),
                "mode": state.get("mode"),
                "output": int(bool(state.get("output"))),
            })
            self.file.flush()
            self.rows += 1
        if self.rows % 10 == 0:
            self.broker.publish("logger", self.info())

    # --- súbory ---
    def list(self):
        out = []
        for fn in sorted(os.listdir(self.folder), reverse=True):
            if not fn.endswith(".csv"):
                continue
            p = os.path.join(self.folder, fn)
            st = os.stat(p)
            out.append({"name": fn, "size": st.st_size, "mtime": st.st_mtime, "active": fn == self.name and self.active})
        return out

    def path(self, name):
        name = os.path.basename(name)
        p = os.path.join(self.folder, name)
        if not os.path.isfile(p):
            raise FileNotFoundError(name)
        return p

    def read(self, name, limit=5000):
        with open(self.path(name), newline="") as f:
            rows = list(csv.DictReader(f))
        total = len(rows)
        if limit and total > limit:
            step = total / limit
            rows = [rows[int(i * step)] for i in range(limit)]
        return {"total": total, "rows": rows}

    def delete(self, name):
        p = self.path(name)
        if self.active and os.path.basename(p) == self.name:
            self.stop()
        os.remove(p)


class EventLog:
    def __init__(self, path, broker, keep=500):
        self.path = path
        self.broker = broker
        self.items = collections.deque(maxlen=keep)
        self.lock = threading.Lock()

    def add(self, msg, kind="info"):
        e = {"t": time.time(), "kind": kind, "msg": str(msg)}
        with self.lock:
            self.items.append(e)
            try:
                with open(self.path, "a") as f:
                    f.write(f"{datetime.fromtimestamp(e['t']).isoformat(timespec='seconds')} [{kind}] {msg}\n")
            except OSError:
                pass
        self.broker.publish("event", e)
        return e

    def list(self, limit=200):
        with self.lock:
            return list(self.items)[-limit:]
