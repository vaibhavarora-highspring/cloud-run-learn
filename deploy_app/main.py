import os
import time
from datetime import datetime, timedelta
from flask import Flask, jsonify, render_template_string

app = Flask(__name__)

# --- GLOBAL CONFIGURATION ---
START_TIME = time.time()
MAX_LOG_ENTRIES = 100  # Limits history so the list doesn't grow forever
DETAILED_LOGS = [] 
CPU_HISTORY = []
MEMORY_HISTORY = []

# Initialize with zeros; will be 'primed' in the __main__ block
PREV_CPU = {"user": 0, "nice": 0, "system": 0, "idle": 0, "iowait": 0, "irq": 0, "softirq": 0, "steal": 0}

# --- UTILITY FUNCTIONS ---

def format_uptime(seconds):
    """Converts raw seconds into a 'Days, Hours, Minutes, Seconds' string."""
    td = timedelta(seconds=int(seconds))
    days = td.days
    hours, remainder = divmod(td.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    parts = []
    if days > 0: parts.append(f"{days}d")
    if hours > 0: parts.append(f"{hours}h")
    if minutes > 0: parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    return " ".join(parts)

def read_cpu_times():
    """Reads raw ticks from the Linux kernel /proc/stat file."""
    try:
        with open("/proc/stat", "r") as f:
            parts = f.readline().split()
            return {
                "user": float(parts[1]), "nice": float(parts[2]), "system": float(parts[3]),
                "idle": float(parts[4]), "iowait": float(parts[5]), "irq": float(parts[6]),
                "softirq": float(parts[7]), "steal": float(parts[8])
            }
    except (FileNotFoundError, IndexError):
        # Fallback for non-Linux testing environments (Windows/Mac)
        return {k: 0.0 for k in PREV_CPU.keys()}

def get_cpu_metric():
    global PREV_CPU
    current = read_cpu_times()
    
    # Logic: Calculate the change since the last time this function was called
    prev_idle = PREV_CPU["idle"] + PREV_CPU["iowait"]
    idle = current["idle"] + current["iowait"]
    prev_total = sum(PREV_CPU.values())
    total = sum(current.values())

    total_delta = total - prev_total
    idle_delta = idle - prev_idle
    
    # Percentage = (1 - ratio of idle time) * 100
    cpu_percent = (1 - idle_delta / total_delta) * 100 if total_delta > 0 else 0
    
    # Store the current reading for the NEXT calculation
    PREV_CPU = current
    CPU_HISTORY.append(cpu_percent)
    
    if len(CPU_HISTORY) > MAX_LOG_ENTRIES: CPU_HISTORY.pop(0)
    
    return {
        "current": round(cpu_percent, 2),
        "highest": round(max(CPU_HISTORY) if CPU_HISTORY else 0, 2),
        "lowest": round(min(CPU_HISTORY) if CPU_HISTORY else 0, 2),
        "running_average": round(sum(CPU_HISTORY) / len(CPU_HISTORY), 2)
    }

def get_memory_metric():
    meminfo = {}
    try:
        with open("/proc/meminfo", "r") as f:
            for line in f:
                parts = line.split(":")
                if len(parts) == 2:
                    # Key: MemTotal, Value: 123456 (ignoring 'kB')
                    meminfo[parts[0].strip()] = int(parts[1].strip().split()[0])
    except FileNotFoundError:
        return {"total_mb": 0, "used_mb": 0, "available_mb": 0, "current": 0}

    total = meminfo.get("MemTotal", 1)
    # Use MemAvailable (Modern Linux) or MemFree (Old Linux)
    available = meminfo.get("MemAvailable", meminfo.get("MemFree", 0))
    used = total - available
    percent = (used / total) * 100
    
    MEMORY_HISTORY.append(percent)
    if len(MEMORY_HISTORY) > MAX_LOG_ENTRIES: MEMORY_HISTORY.pop(0)

    return {
        "total_mb": round(total / 1024, 2),
        "used_mb": round(used / 1024, 2),
        "available_mb": round(available / 1024, 2),
        "current": round(percent, 2),
        "highest": round(max(MEMORY_HISTORY), 2),
        "lowest": round(min(MEMORY_HISTORY), 2)
    }

def calculate_health_score(cpu_percent, memory_percent, uptime_seconds):
    """Grading algorithm: 100 = Perfect, 0 = Emergency."""
    score = 100.0
    
    # CPU Penalties (Exponential growth after 70%)
    if cpu_percent < 30: score -= (cpu_percent * 0.5)
    elif cpu_percent < 70: score -= (15 + (cpu_percent - 30) * 1.0)
    else: score -= (55 + (cpu_percent - 70) * 1.5)
    
    # Memory Penalties (Exponential growth after 80%)
    if memory_percent < 50: score -= (memory_percent * 0.4)
    elif memory_percent < 80: score -= (20 + (memory_percent - 50) * 1.0)
    else: score -= (50 + (memory_percent - 80) * 1.5)

    # Stability Bonus: Rewards servers that don't crash
    if uptime_seconds > 3600: score += min(10, uptime_seconds / 3600)
    elif uptime_seconds > 300: score += 5
    
    # Flat critical deductions
    if cpu_percent > 90: score -= 15
    if memory_percent > 90: score -= 15
    
    return round(max(0, min(100, score)))

# --- HTML TEMPLATE ---

BASE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Cloud Run Monitor</title>
    <style>
        body { background: #0a0a0a; color: #fff; font-family: 'Courier New', monospace; 
               display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0;
               background-image: linear-gradient(rgba(30,30,30,0.5) 1px, transparent 1px), 
                                 linear-gradient(90deg, rgba(30,30,30,0.5) 1px, transparent 1px);
               background-size: 20px 20px; }
        .box { border: 1px solid #444; padding: 30px; width: 550px; background: rgba(0,0,0,0.9); position: relative; }
        .dot { width: 8px; height: 8px; background: #569cd6; position: absolute; border-radius: 50%; }
        .tl{top:-4px;left:-4px} .tr{top:-4px;right:-4px} .bl{bottom:-4px;left:-4px} .br{bottom:-4px;right:-4px}
        .btn { display: block; margin: 15px auto; padding: 10px; border: 1px solid #569cd6; color: #569cd6; 
               text-decoration: none; text-align: center; cursor: pointer; }
        .btn:hover { background: #569cd6; color: #000; }
        .log-container { height: 250px; overflow-y: auto; background: #050505; border: 1px solid #222; padding: 10px; }
        .log-entry { font-size: 12px; border-bottom: 1px solid #111; padding: 4px 0; color: #85c46c; }
        .log-time { color: #569cd6; }
    </style>
</head>
<body>
    <div class="box">
        <div class="dot tl"></div><div class="dot tr"></div>
        <div class="dot bl"></div><div class="dot br"></div>
        {{ content | safe }}
    </div>
</body>
</html>
"""

# --- ROUTES ---

@app.route('/')
def root():
    uptime_str = format_uptime(time.time() - START_TIME)
    content = f"""
        <h2 style="text-align:center">Cloud Run Controller</h2>
        <p style="color:#888; text-align:center">Uptime: <strong>{uptime_str}</strong></p>
        <p style="color:#444; text-align:center; font-size:12px;">System scan ready.</p>
        <a href="/analyze" class="btn">RUN PERFORMANCE ANALYSIS</a>
        <a href="/logs" class="btn" style="border-color:#85c46c; color:#85c46c;">VIEW RECENT HISTORY</a>
    """
    return render_template_string(BASE_HTML, content=content)

@app.route('/analyze')
def analyze():
    cpu = get_cpu_metric()
    mem = get_memory_metric()
    uptime_sec = time.time() - START_TIME
    score = calculate_health_score(cpu['current'], mem['current'], uptime_sec)
    
    # Store log with readable time
    timestamp_readable = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    DETAILED_LOGS.append({
        "time": timestamp_readable,
        "cpu": cpu['current'],
        "mem": mem['current'],
        "score": score
    })
    
    if len(DETAILED_LOGS) > MAX_LOG_ENTRIES: DETAILED_LOGS.pop(0)
    
    return jsonify({
        "timestamp": timestamp_readable,
        "up_time_readable": format_uptime(uptime_sec),
        "health_score": score,
        "cpu_metric": cpu,
        "memory_metric": mem,
        "status": "Healthy" if score > 70 else "Under Stress"
    })

@app.route('/logs')
def logs():
    log_rows = ""
    for entry in reversed(DETAILED_LOGS):
        log_rows += f'<div class="log-entry"><span class="log-time">[{entry["time"]}]</span> CPU: {entry["cpu"]}% | MEM: {entry["mem"]}% | Score: {entry["score"]}</div>'
    
    content = f"""
        <h3 style="margin-top:0">Operational History</h3>
        <div class="log-container">
            {log_rows if log_rows else '<div style="color:#444">No analysis data yet.</div>'}
        </div>
        <a href="/" class="btn">BACK TO DASHBOARD</a>
    """
    return render_template_string(BASE_HTML, content=content)

if __name__ == "__main__":
    # IMPORTANT: Initial 'prime' of CPU stats to prevent zero-subtraction on first click
    PREV_CPU = read_cpu_times()
    
    # Cloud Run dynamic port handling
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)