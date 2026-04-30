import paramiko

def execute_remote_script():
    host = "115.191.10.107"
    port = 22
    username = "root"
    password = "Zxcv1234@"
    
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(host, port, username, password)
        commands = [
            "cd /root/.openclaw/workspace/projects/Finance && git pull origin master",
            "pkill -9 -f 'uvicorn' || true",
            "pkill -9 -f 'multiprocessing.spawn' || true",
            "cd /root/.openclaw/workspace/projects/Finance/backend && source /root/.local/share/virtualenvs/backend-*/bin/activate 2>/dev/null || true && nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload > backend.log 2>&1 &",
            "pkill -9 -f 'npm run dev' || true",
            "pkill -9 -f 'vite' || true",
            "cd /root/.openclaw/workspace/projects/Finance/frontend && rm -f .env.local && nohup npm run dev -- --host 0.0.0.0 > frontend.log 2>&1 &",
            "sleep 3",
            "echo 'Restarted successfully.'"
        ]
        
        for cmd in commands:
            print(f"\nExecuting: {cmd}")
            stdin, stdout, stderr = ssh.exec_command(cmd)
            out = stdout.read().decode('utf-8').strip()
            err = stderr.read().decode('utf-8').strip()
            if out:
                print("STDOUT:")
                print(out)
            if err:
                print("STDERR:")
                print(err)
    except Exception as e:
        print(f"Connection failed: {e}")
    finally:
        ssh.close()

if __name__ == "__main__":
    execute_remote_script()
