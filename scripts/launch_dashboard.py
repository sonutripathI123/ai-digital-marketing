import os
import sys
import socket
import subprocess
import time
import urllib.request
import webbrowser

def is_server_healthy(host="127.0.0.1", port=8000, timeout=1.0):
    url = f"http://{host}:{port}/api/overview"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "DashboardLauncher/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status == 200
    except Exception:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(timeout)
                return s.connect_ex((host, port)) == 0
        except Exception:
            return False

def main():
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Locate python executable
    venv_python = os.path.join(project_dir, 'corporate-cars-social-agent', '.venv', 'Scripts', 'python.exe')
    if not os.path.exists(venv_python):
        venv_python = sys.executable

    # If server is not yet running, start it
    if not is_server_healthy():
        creationflags = 0
        if os.name == 'nt':
            # DETACHED_PROCESS (0x00000008) | CREATE_NEW_PROCESS_GROUP (0x00000200) | CREATE_NO_WINDOW (0x08000000)
            creationflags = 0x00000008 | 0x00000200 | 0x08000000

        log_dir = os.path.join(project_dir, 'logs')
        os.makedirs(log_dir, exist_ok=True)
        log_file = open(os.path.join(log_dir, 'dashboard_server.log'), 'a', encoding='utf-8')

        subprocess.Popen(
            [venv_python, '-m', 'uvicorn', 'dashboard.api:app', '--host', '127.0.0.1', '--port', '8000'],
            cwd=project_dir,
            creationflags=creationflags,
            stdout=log_file,
            stderr=log_file,
            close_fds=True
        )

        # Poll until the backend is confirmed healthy (up to 12 seconds)
        for _ in range(24):
            time.sleep(0.5)
            if is_server_healthy():
                break

    # Open the dashboard URL in browser
    webbrowser.open('http://127.0.0.1:8000')

if __name__ == '__main__':
    main()

