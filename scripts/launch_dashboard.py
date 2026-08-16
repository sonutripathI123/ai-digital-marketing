import os
import sys
import socket
import subprocess
import time
import webbrowser

def is_port_open(host="127.0.0.1", port=8000):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            return s.connect_ex((host, port)) == 0
    except Exception:
        return False

def main():
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    venv_python = os.path.join(project_dir, 'corporate-cars-social-agent', '.venv', 'Scripts', 'python.exe')
    if not os.path.exists(venv_python):
        venv_python = sys.executable

    # Check if Uvicorn server is running on port 8000
    if not is_port_open("127.0.0.1", 8000):
        # DETACHED_PROCESS flag on Windows
        creationflags = 0x00000008 | 0x00000200 if os.name == 'nt' else 0
        subprocess.Popen(
            [venv_python, '-m', 'uvicorn', 'dashboard.api:app', '--host', '127.0.0.1', '--port', '8000'],
            cwd=project_dir,
            creationflags=creationflags,
            close_fds=True
        )
        time.sleep(2.5)

    # Open browser
    webbrowser.open('http://127.0.0.1:8000')

if __name__ == '__main__':
    main()
