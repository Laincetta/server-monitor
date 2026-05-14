import psutil, os, time, logging, threading, platform
from datetime import datetime
from collections import deque
from flask import Flask, render_template, jsonify

THRESHOLDS = {
    "cpu":      85,
    "ram":      90,
    "disk":     90,
    "cpu_warn": 70,
    "ram_warn": 80,
}

LOG_FILE    = os.path.join(os.path.dirname(__file__), "logs", "monitor.log")
HISTORY_LEN = 60

os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("monitor")

history = {
    "time":    deque(maxlen=HISTORY_LEN),
    "cpu":     deque(maxlen=HISTORY_LEN),
    "ram":     deque(maxlen=HISTORY_LEN),
    "disk":    deque(maxlen=HISTORY_LEN),
    "net_in":  deque(maxlen=HISTORY_LEN),
    "net_out": deque(maxlen=HISTORY_LEN),
}

alerts        = deque(maxlen=50)
sec_events    = deque(maxlen=50)
prev_net      = psutil.net_io_counters()
prev_net_time = time.time()
lock          = threading.Lock()

# кешируем между итерациями, чтобы не дёргать OS в каждом запросе
_stats = {"connections": 0, "users": 0}


def _disk_usage():
    path = 'C:\\' if platform.system() == "Windows" else '/'
    return psutil.disk_usage(path)


def collect_metrics():
    global prev_net, prev_net_time

    # interval=None — неблокирующий вызов, использует время с предыдущего вызова.
    # background_loop спит 1с, поэтому окно измерения ≈1с, а не 2с как при interval=1.
    cpu  = psutil.cpu_percent(interval=None)
    ram  = psutil.virtual_memory().percent
    disk = _disk_usage().percent

    now_net  = psutil.net_io_counters()
    now_time = time.time()
    dt = max(now_time - prev_net_time, 0.001)
    net_in  = round((now_net.bytes_recv - prev_net.bytes_recv) / dt / 1024, 1)
    net_out = round((now_net.bytes_sent - prev_net.bytes_sent) / dt / 1024, 1)
    prev_net      = now_net
    prev_net_time = now_time

    ts = datetime.now().strftime("%H:%M:%S")
    with lock:
        history["time"].append(ts)
        history["cpu"].append(cpu)
        history["ram"].append(ram)
        history["disk"].append(disk)
        history["net_in"].append(net_in)
        history["net_out"].append(net_out)

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


def _add_alert(level, source, msg, kind):
    entry = {"time": datetime.now().strftime("%H:%M:%S"), "level": level,
             "source": source, "msg": msg, "kind": kind}
    with lock:
        if not alerts or alerts[-1]["msg"] != msg:
            alerts.append(entry)
            log.warning("[%s] %s: %s", level, source, msg)


_prev_connections = set()
_prev_users       = set()


def check_security():
    global _prev_connections, _prev_users, _stats

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
                _add_sec_event("ПОЛЬЗОВАТЕЛЬ", f"Новый вход в систему: {u}", "warning")
            for u in _prev_users - current_users:
                _add_sec_event("ПОЛЬЗОВАТЕЛЬ", f"Пользователь вышел: {u}", "info")
        _prev_users = current_users
        with lock:
            _stats["users"] = len(current_users)
    except Exception:
        pass

    try:
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent']):
            try:
                if proc.info['cpu_percent'] and proc.info['cpu_percent'] > 80:
                    _add_sec_event("ПРОЦЕСС",
                        f"'{proc.info['name']}' (PID {proc.info['pid']}) "
                        f"потребляет {proc.info['cpu_percent']}% CPU",
                        "warning")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except Exception:
        pass

    try:
        for proc in psutil.process_iter(['pid', 'name', 'open_files']):
            try:
                files = proc.info.get('open_files') or []
                if len(files) > 500:
                    _add_sec_event("ПРОЦЕСС",
                        f"'{proc.info['name']}' (PID {proc.info['pid']}) "
                        f"открыл {len(files)} файлов",
                        "warning")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except Exception:
        pass


def _add_sec_event(source, msg, kind):
    entry = {"time": datetime.now().strftime("%H:%M:%S"),
             "source": source, "msg": msg, "kind": kind}
    with lock:
        if not sec_events or sec_events[-1]["msg"] != msg:
            sec_events.append(entry)
            log.info("[SEC/%s] %s", source, msg)


def background_loop():
    global _prev_users
    _prev_users = {u.name for u in psutil.users()}
    # прогрев: первый вызов cpu_percent всегда возвращает 0.0
    psutil.cpu_percent(interval=None)
    time.sleep(1)
    log.info("monitor ready at http://0.0.0.0:5000")
    while True:
        try:
            collect_metrics()
            check_security()
        except Exception as e:
            log.error("collect error: %s", e)
        time.sleep(1)


app = Flask(__name__)


@app.route("/")
def index():
    return render_template("dashboard.html")


@app.route("/api/metrics")
def api_metrics():
    # тяжёлые вызовы OS — вне лока
    mem      = psutil.virtual_memory()
    disk_obj = _disk_usage()
    boot     = datetime.fromtimestamp(psutil.boot_time()).strftime("%d.%m.%Y %H:%M")
    cpu_cores = psutil.cpu_count()
    os_str   = f"{platform.system()} {platform.release()}"
    hostname = platform.node()

    with lock:
        return jsonify({
            "cpu":         round(history["cpu"][-1],  1) if history["cpu"]  else 0,
            "ram":         round(history["ram"][-1],  1) if history["ram"]  else 0,
            "disk":        round(history["disk"][-1], 1) if history["disk"] else 0,
            "net_in":      round(history["net_in"][-1],  1) if history["net_in"]  else 0,
            "net_out":     round(history["net_out"][-1], 1) if history["net_out"] else 0,
            "ram_total":   round(mem.total / 1024**3, 1),
            "ram_used":    round(mem.used  / 1024**3, 1),
            "disk_total":  round(disk_obj.total / 1024**3, 1),
            "disk_used":   round(disk_obj.used  / 1024**3, 1),
            "cpu_cores":   cpu_cores,
            "uptime":      boot,
            "os":          os_str,
            "hostname":    hostname,
            "connections": _stats["connections"],
            "users":       _stats["users"],
            "history": {
                "time":    list(history["time"]),
                "cpu":     list(history["cpu"]),
                "ram":     list(history["ram"]),
                "net_in":  list(history["net_in"]),
                "net_out": list(history["net_out"]),
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


@app.route("/api/processes")
def api_processes():
    procs = []
    for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status', 'username']):
        try:
            procs.append({
                "pid":    p.info['pid'],
                "name":   p.info['name'] or "-",
                "cpu":    round(p.info['cpu_percent'] or 0, 1),
                "mem":    round(p.info['memory_percent'] or 0, 1),
                "status": p.info['status'],
                "user":   p.info['username'] or "-",
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    procs.sort(key=lambda x: x['cpu'], reverse=True)
    return jsonify(procs[:30])


if __name__ == "__main__":
    threading.Thread(target=background_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
