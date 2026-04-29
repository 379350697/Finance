import paramiko
import time

def execute_remote_script():
    host = "115.191.10.107"
    port = 22
    username = "root"
    password = "Zxcv1234@"
    
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print(f"Connecting to {host}...")
        ssh.connect(host, port, username, password)
        print("Connected.")
        
        # Define project paths
        project_dir = "/root/.openclaw/workspace/projects/Finance"
        backend_dir = f"{project_dir}/backend"
        frontend_dir = f"{project_dir}/frontend"
        
        commands = [
            "echo '=== Finding and stopping backend ==='",
            "pkill -f 'uvicorn app.main:app' || echo 'No backend running'",
            "pkill -f 'celery -A app.core.celery_app worker' || echo 'No celery worker running'",
            "echo '=== Finding and stopping frontend ==='",
            "pkill -f 'npm run dev' || echo 'No frontend running'",
            "pkill -f 'vite' || echo 'No vite running'",
            
            "echo '=== Pulling latest codebase ==='",
            f"cd {project_dir} && git fetch origin master && git reset --hard origin/master",
            
            "echo '=== Running backend database migrations ==='",
            f"cd {backend_dir} && source /root/.local/share/virtualenvs/backend-*/bin/activate 2>/dev/null || true && alembic upgrade head || /root/.local/bin/poetry run alembic upgrade head || echo 'Alembic failed, trying direct python' && python3 -m alembic upgrade head",
            
            "echo '=== Starting backend ==='",
            f"cd {backend_dir} && nohup /root/.local/bin/poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload > backend.log 2>&1 &",
            
            "echo '=== Installing frontend dependencies ==='",
            f"cd {frontend_dir} && npm install",
            
            "echo '=== Starting frontend ==='",
            f"cd {frontend_dir} && nohup npm run dev -- --host 0.0.0.0 > frontend.log 2>&1 &",
            
            "echo '=== Waiting a few seconds for services to start ==='",
            "sleep 3",
            
            "echo '=== Checking running processes ==='",
            "ps aux | grep -E 'uvicorn|vite|npm run dev' | grep -v grep"
        ]
        
        for cmd in commands:
            print(f"\nExecuting: {cmd}")
            stdin, stdout, stderr = ssh.exec_command(cmd)
            out = stdout.read().decode('utf-8').strip()
            err = stderr.read().decode('utf-8').strip()
            
            if out:
                print("STDOUT:")
                print(out)
            if err and "npm WARN" not in err:
                print("STDERR:")
                print(err)
            
        print("\nDeployment successful.")
        
    except Exception as e:
        print(f"Connection/Execution failed: {e}")
    finally:
        ssh.close()

if __name__ == "__main__":
    execute_remote_script()
