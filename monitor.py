import os
import time
import logging
import threading
import platform
from datetime import datetime
from collections import deque
from logging.handlers import RotatingFileHandler

import psutil
from flask import Flask, render_template, jsonify

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── Configuration ──────────────────────────────────────────────────────────────
HOST        = os.getenv("MONITOR_HOST", "0.0.0.0")
PORT        = int(os.getenv("MONITOR_PORT", "5000"))
LOG_DIR     = os.getenv("MONITOR_LOG_DIR",
                        os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs"))
LOG_FILE    = os.path.join(LOG_DIR, "monitor.log")
HISTORY_LEN = int(os.getenv("MONITOR_HISTORY", "60"))

THRESHOLDS = {
    "cpu":      int(os.getenv("THRESHOLD_CPU_CRIT",  "85")),
    "ram":      int(os.getenv("THRESHOLD_RAM_CRIT",  "90")),
    "disk":     int(os.getenv("THRESHOLD_DISK_CRIT", "90")),
    "cpu_warn": int(os.getenv("THRESHOLD_CPU_WARN",  "70")),
    "ram_warn": int(os.getenv("THRESHOLD_RAM_WARN",  "80")),
}

# ── Logging (10 MB per file, 5 backups) ────────────────────────────────────────
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        RotatingFileHandler(LOG_FILE, maxBytes=10 * 1024 * 1024,
                            backupCount=5, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("monitor")

# ── Shared in-memory state ─────────────────────────────────────────────────────
history = {
    "time":       deque(maxlen=HISTORY_LEN),
    "cpu":        deque(maxlen=HISTORY_LEN),
    "ram":        deque(maxlen=HISTORY_LEN),
    "disk":       deque(maxlen=HISTORY_LEN),
    "net_in":     deque(maxlen=HISTORY_LEN),
    "net_out":    deque(maxlen=HISTORY_LEN),
    "disk_read":  deque(maxlen=HISTORY_LEN),
    "disk_write": deque(maxlen=HISTORY_LEN),
}

alerts     = deque(maxlen=50)
sec_events = deque(maxlen=50)
lock       = threading.Lock()

prev_net         = psutil.net_io_counters()
prev_disk        = psutil.disk_io_counters()
prev_sample_time = time.time()

_stats = {"connections": 0, "users": 0}


# ── Helpers ────────────────────────────────────────────────────────────────────
def _disk_path() -> str:
    return "C:\\" if platform.system() == "Windows" else "/"


def _disk_usage():
    return psutil.disk_usage(_disk_path())


# ── Metrics collection ─────────────────────────────────────────────────────────
def collect_metrics() -> None:
    global prev_net, prev_disk, prev_sample_time

    cpu  = psutil.cpu_percent(interval=None)
    ram  = psutil.virtual_memory().percent
    disk = _disk_usage().percent

    now_net  = psutil.net_io_counters()
    now_disk = psutil.disk_io_counters()
    now_time = time.time()
    dt = max(now_time - prev_sample_time, 0.001)

    net_in  = round((now_net.bytes_recv - prev_net.bytes_recv) / dt / 1024, 1)
    net_out = round((now_net.bytes_sent - prev_net.bytes_sent) / dt / 1024, 1)

    if now_disk and prev_disk:
        disk_read  = round((now_disk.read_bytes  - prev_disk.read_bytes)  / dt / 1024, 1)
        disk_write = round((now_disk.write_bytes - prev_disk.write_bytes) / dt / 1024, 1)
    else:
        disk_read = disk_write = 0.0

    prev_net         = now_net
    prev_disk        = now_disk
    prev_sample_time = now_time

    ts = datetime.now().strftime("%H:%M:%S")
    with lock:
        history["time"].append(ts)
        history["cpu"].append(cpu)
        history["ram"].append(ram)
        history["disk"].append(disk)
        history["net_in"].append(net_in)
        history["net_out"].append(net_out)
        history["disk_read"].append(max(disk_read, 0))
        history["disk_write"].append(max(disk_write, 0))

    if cpu >= THRESHOLDS["cpu"]:
        _add_alert("КРИТИЧНО", "CPU", f"Загрузка CPU: {cpu}%", "danger")
    elif cpu >= THRESHOLDS["cpu_warn"]:
        _add_alert("ВНИМАНИЕ", "CPU", f"Загрузка CPU: {cpu}%", "warning")

    if ram >= THRESHOLDS["ram"]:
        _add_alert("КРИТИЧНО", "RAM", f"Использование памяти: {ram}%", "danger")
    elif ram >= THRESHOLDS["ram_warn"]:
        _add_alert("ВНИМАНИЕ", "RAM", f"Использование памяти: {ram}%", "warning")

    if disk >= THRESHOLDS["disk"]:
        _add_alert("КРИТИЧНО", "ДИСК", f"Заполнен на {disk}%", "danger")


def _add_alert(level: str, source: str, msg: str, kind: str) -> None:
    entry = {"time": datetime.now().strftime("%H:%M:%S"),
             "level": level, "source": source, "msg": msg, "kind": kind}
    with lock:
        if not alerts or alerts[-1]["msg"] != msg:
            alerts.append(entry)
            log.warning("[%s] %s: %s", level, source, msg)


# ── Security monitoring ────────────────────────────────────────────────────────
_prev_connections: set = set()
_prev_users:       set = set()


def check_security() -> None:
    global _prev_connections, _prev_users

    try:
        conns = psutil.net_connections(kind="inet")
        current = {
            (c.laddr, c.raddr, c.status)
            for c in conns
            if c.status == "ESTABLISHED" and c.raddr
        }
        for laddr, raddr, _ in current - _prev_connections:
            _add_sec_event("СЕТЬ",
                f"Новое подключение: {laddr.ip}:{laddr.port} -> {raddr.ip}:{raddr.port}",
                "info")
        _prev_connections = current
        with lock:
            _stats["connections"] = len(current)
    except Exception:
        pass

    try:
        current_users = {u.name for u in psutil.users()}
        if _prev_users:
            for u in current_users - _prev_users:
                _add_sec_event("ПОЛЬЗОВАТЕЛЬ", f"Новый вход: {u}", "warning")
            for u in _prev_users - current_users:
                _add_sec_event("ПОЛЬЗОВАТЕЛЬ", f"Пользователь вышел: {u}", "info")
        _prev_users = current_users
        with lock:
            _stats["users"] = len(current_users)
    except Exception:
        pass

    try:
        for proc in psutil.process_iter(["pid", "name", "cpu_percent"]):
            try:
                if proc.info["cpu_percent"] and proc.info["cpu_percent"] > 80:
                    _add_sec_event("ПРОЦЕСС",
                        f"'{proc.info['name']}' (PID {proc.info['pid']}) "
                        f"потребляет {proc.info['cpu_percent']}% CPU",
                        "warning")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except Exception:
        pass

    try:
        for proc in psutil.process_iter(["pid", "name", "open_files"]):
            try:
                files = proc.info.get("open_files") or []
                if len(files) > 500:
                    _add_sec_event("ПРОЦЕСС",
                        f"'{proc.info['name']}' (PID {proc.info['pid']}) "
                        f"открыл {len(files)} файлов",
                        "warning")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except Exception:
        pass


def _add_sec_event(source: str, msg: str, kind: str) -> None:
    entry = {"time": datetime.now().strftime("%H:%M:%S"),
             "source": source, "msg": msg, "kind": kind}
    with lock:
        if not sec_events or sec_events[-1]["msg"] != msg:
            sec_events.append(entry)
            log.info("[SEC/%s] %s", source, msg)


# ── Background collection thread ───────────────────────────────────────────────
def background_loop() -> None:
    global _prev_users
    _prev_users = {u.name for u in psutil.users()}
    psutil.cpu_percent(interval=None)   # warm-up: first call always returns 0
    time.sleep(1)
    log.info("Monitor ready — http://%s:%d", HOST, PORT)
    while True:
        try:
            collect_metrics()
            check_security()
        except Exception as e:
            log.error("Collection error: %s", e)
        time.sleep(1)


# ── Flask application ──────────────────────────────────────────────────────────
app = Flask(__name__)


@app.route("/")
def index():
    return render_template("dashboard.html")


@app.route("/health")
def health():
    """Endpoint for load-balancers and container orchestrators."""
    return jsonify({"status": "ok"})


@app.route("/api/metrics")
def api_metrics():
    mem      = psutil.virtual_memory()
    disk_obj = _disk_usage()
    boot     = datetime.fromtimestamp(psutil.boot_time()).strftime("%d.%m.%Y %H:%M")
    try:
        load     = psutil.getloadavg()
        load_avg = f"{load[0]:.2f} {load[1]:.2f} {load[2]:.2f}"
    except AttributeError:
        load_avg = None

    with lock:
        return jsonify({
            "cpu":         round(history["cpu"][-1],  1) if history["cpu"]  else 0,
            "ram":         round(history["ram"][-1],  1) if history["ram"]  else 0,
            "disk":        round(history["disk"][-1], 1) if history["disk"] else 0,
            "net_in":      round(history["net_in"][-1],  1) if history["net_in"]  else 0,
            "net_out":     round(history["net_out"][-1], 1) if history["net_out"] else 0,
            "ram_total":   round(mem.total    / 1024 ** 3, 1),
            "ram_used":    round(mem.used     / 1024 ** 3, 1),
            "disk_total":  round(disk_obj.total / 1024 ** 3, 1),
            "disk_used":   round(disk_obj.used  / 1024 ** 3, 1),
            "disk_path":   _disk_path(),
            "cpu_cores":   psutil.cpu_count(),
            "uptime":      boot,
            "os":          f"{platform.system()} {platform.release()}",
            "hostname":    platform.node(),
            "load_avg":    load_avg,
            "connections": _stats["connections"],
            "users":       _stats["users"],
            "history": {
                "time":       list(history["time"]),
                "cpu":        list(history["cpu"]),
                "ram":        list(history["ram"]),
                "net_in":     list(history["net_in"]),
                "net_out":    list(history["net_out"]),
                "disk_read":  list(history["disk_read"]),
                "disk_write": list(history["disk_write"]),
            },
        })


@app.route("/api/alerts")
def api_alerts():
    with lock:
        return jsonify(list(reversed(alerts)))


@app.route("/api/security")
def api_security():
    with lock:
        return jsonify(list(reversed(sec_events)))


@app.route("/api/connections")
def api_connections():
    try:
        conns     = psutil.net_connections(kind="inet")
        pid_cache = {}
        result    = []
        for c in conns:
            if not c.laddr:
                continue
            pid = c.pid
            if pid and pid not in pid_cache:
                try:
                    pid_cache[pid] = psutil.Process(pid).name()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pid_cache[pid] = "-"
            result.append({
                "laddr":   f"{c.laddr.ip}:{c.laddr.port}",
                "raddr":   f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else "-",
                "status":  c.status,
                "process": pid_cache.get(pid, "-") if pid else "-",
            })
        result.sort(key=lambda x: (x["status"] != "ESTABLISHED", x["status"]))
        return jsonify(result[:50])
    except Exception as e:
        log.error("connections error: %s", e)
        return jsonify([])


@app.route("/api/processes")
def api_processes():
    procs = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent",
                                   "memory_percent", "status", "username"]):
        try:
            procs.append({
                "pid":    p.info["pid"],
                "name":   p.info["name"] or "-",
                "cpu":    round(p.info["cpu_percent"] or 0, 1),
                "mem":    round(p.info["memory_percent"] or 0, 1),
                "status": p.info["status"],
                "user":   p.info["username"] or "-",
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    procs.sort(key=lambda x: x["cpu"], reverse=True)
    return jsonify(procs[:30])


# ── Start background thread at import time (works with gunicorn / waitress) ────
threading.Thread(target=background_loop, daemon=True).start()

if __name__ == "__main__":
    app.run(host=HOST, port=PORT, debug=False, use_reloader=False)
