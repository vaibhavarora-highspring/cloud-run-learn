import os
import time
from datetime import datetime
from flask import Flask, jsonify, render_template_string

app = Flask(__name__)


START_TIME = time.time()
DETAILED_LOGS = [] 
CPU_HISTORY = []
MEMORY_HISTORY = []
PREV_CPU = {"user": 0, "nice": 0, "system": 0, "idle": 0, "iowait": 0, "irq": 0, "softirq": 0, "steal": 0}


def read_cpu_times():
    with open("/proc/stat", "r") as f:
        parts = f.readline().split()
        return {
            "user": float(parts[1]), "nice": float(parts[2]), "system": float(parts[3]),
            "idle": float(parts[4]), "iowait": float(parts[5]), "irq": float(parts[6]),
            "softirq": float(parts[7]), "steal": float(parts[8])
        }

def get_cpu_metric():
    global PREV_CPU
    time.sleep(1)
    current = read_cpu_times()
    
    prev_idle = PREV_CPU["idle"] + PREV_CPU["iowait"]
    idle = current["idle"] + current["iowait"]
    prev_total = sum(PREV_CPU.values())
    total = sum(current.values())

    total_delta = total - prev_total
    idle_delta = idle - prev_idle
    cpu_percent = (1 - idle_delta / total_delta) * 100 if total_delta > 0 else 0
    
    PREV_CPU = current
    CPU_HISTORY.append(cpu_percent)
    return {
        "current": round(cpu_percent, 2),
        "highest": round(max(CPU_HISTORY), 2),
        "lowest": round(min(CPU_HISTORY), 2),
        "running_average": round(sum(CPU_HISTORY) / len(CPU_HISTORY), 2)
    }

def get_memory_metric():
    meminfo = {}
    with open("/proc/meminfo", "r") as f:
        for line in f:
            parts = line.split(":")
            if len(parts) == 2:
                meminfo[parts[0].strip()] = int(parts[1].strip().split()[0])

    total = meminfo["MemTotal"]
    available = meminfo.get("MemAvailable", meminfo.get("MemFree", 0))
    used = total - available
    percent = (used / total) * 100
    
    MEMORY_HISTORY.append(percent)
    return {
        "total_mb": round(total / 1024, 2),
        "used_mb": round(used / 1024, 2),
        "available_mb": round(available / 1024, 2),
        "current": round(percent, 2),
        "highest": round(max(MEMORY_HISTORY), 2),
        "lowest": round(min(MEMORY_HISTORY), 2)
    }


def calculate_health_score(cpu_percent, memory_percent, uptime_seconds):
    score = 100.0

  
    if cpu_percent < 30:
        cpu_penalty = cpu_percent * 0.5 
    elif cpu_percent < 70:
        cpu_penalty = 15 + (cpu_percent - 30) * 1.0 
    else:
        cpu_penalty = 55 + (cpu_percent - 70) * 1.5  
    score -= cpu_penalty
    
  
    if memory_percent < 50:
        memory_penalty = memory_percent * 0.4 
    elif memory_percent < 80:
        memory_penalty = 20 + (memory_percent - 50) * 1.0 
    else:
        memory_penalty = 50 + (memory_percent - 80) * 1.5  
    score -= memory_penalty

  
    if uptime_seconds > 3600: 
        uptime_bonus = min(10, uptime_seconds / 3600)  
    elif uptime_seconds > 300: 
        uptime_bonus = 5
    else:
        uptime_bonus = 0  
    score += uptime_bonus
    
   
    if cpu_percent > 90: score -= 15 
    if memory_percent > 90: score -= 15 
    
    return round(max(0, min(100, score)))

def generate_status_message(health_score):
    if health_score >= 90: return "Excellent - System running optimally"
    elif health_score >= 75: return "Good - System performing well"
    elif health_score >= 60: return "Fair - System under moderate load"
    elif health_score >= 40: return "Warning - System experiencing elevated resource usage"
    elif health_score >= 20: return "Critical - System resources heavily strained"
    else: return "Emergency - System resources critically exhausted"


BASE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <style>
        body { background: #0a0a0a; color: #fff; font-family: 'Courier New', monospace; 
               display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0;
               background-image: linear-gradient(rgba(30,30,30,0.5) 1px, transparent 1px), 
                                 linear-gradient(90deg, rgba(30,30,30,0.5) 1px, transparent 1px);
               background-size: 20px 20px; }
        .box { border: 1px solid #444; padding: 30px; width: 500px; background: rgba(0,0,0,0.9); position: relative; }
        .dot { width: 8px; height: 8px; background: #569cd6; position: absolute; border-radius: 50%; }
        .tl{top:-4px;left:-4px} .tr{top:-4px;right:-4px} .bl{bottom:-4px;left:-4px} .br{bottom:-4px;right:-4px}
        .btn { display: block; margin: 15px auto; padding: 10px; border: 1px solid #569cd6; color: #569cd6; 
               text-decoration: none; text-align: center; }
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

@app.route('/')
def root():
    content = """
        <h2 style="text-align:center">Cloud Run Controller</h2>
        <p style="color:#888; text-align:center">Hello from Cloud Run! System check complete.</p>
        <a href="/analyze" class="btn">VIEW ANALYTICS (JSON)</a>
        <a href="/logs" class="btn" style="border-color:#85c46c; color:#85c46c;">VIEW SYSTEM LOGS</a>
    """
    return render_template_string(BASE_HTML, content=content)

@app.route('/analyze')
def analyze():
    cpu = get_cpu_metric()
    mem = get_memory_metric()
    uptime = time.time() - START_TIME
    score = calculate_health_score(cpu['current'], mem['current'], uptime)
    
    DETAILED_LOGS.append({
        "time": datetime.now().strftime("%H:%M:%S"),
        "cpu": cpu['current'],
        "mem": mem['current'],
        "score": score
    })
    
    return jsonify({
        "timestamp": int(time.time()),
        "up_time": "99%",
        "cpu_metric": cpu,
        "memory_metric": mem,
        "health_score": score,
        "message": generate_status_message(score)
    })

@app.route('/logs')
def logs():
    log_rows = ""
    for entry in reversed(DETAILED_LOGS):
        log_rows += f'<div class="log-entry"><span class="log-time">[{entry["time"]}]</span> CPU: {entry["cpu"]}% | MEM: {entry["mem"]}% | Score: {entry["score"]}</div>'
    
    content = f"""
        <h3 style="margin-top:0">Operational History</h3>
        <div class="log-container">
            {log_rows if log_rows else '<div style="color:#444">No data recorded.</div>'}
        </div>
        <a href="/" class="btn">BACK TO HOME</a>
    """
    return render_template_string(BASE_HTML, content=content)

if __name__ == "__main__":
    PREV_CPU = read_cpu_times()
    app.run(host='0.0.0.0', port=8080)