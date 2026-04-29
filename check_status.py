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
            "pkill -f 'uvicorn app.main:app' || true",
            "cd /root/.openclaw/workspace/projects/Finance/backend && source /root/.local/share/virtualenvs/backend-*/bin/activate 2>/dev/null || true && nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload > backend.log 2>&1 &",
            "sleep 3",
            "ps aux | grep -E 'uvicorn' | grep -v grep",
        ]
        
        for cmd in commands:
            print(f"\nExecuting: {cmd}")
            stdin, stdout, stderr = ssh.exec_command(cmd)
            out = stdout.read().decode('utf-8').strip()
            if out:
                print("STDOUT:")
                print(out)
    except Exception as e:
        print(f"Connection failed: {e}")
    finally:
        ssh.close()

if __name__ == "__main__":
    execute_remote_script()
