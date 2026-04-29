import paramiko

def check_frontend_logs():
    host = "115.191.10.107"
    port = 22
    username = "root"
    password = "Zxcv1234@"
    
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(host, port, username, password)
        commands = [
            "cat /root/.openclaw/workspace/projects/Finance/frontend/frontend.log"
        ]
        
        for cmd in commands:
            print(f"\nExecuting: {cmd}")
            stdin, stdout, stderr = ssh.exec_command(cmd)
            out = stdout.read().decode('utf-8').strip()
            if out:
                print("STDOUT:")
                print(out)
    except Exception as e:
        pass

check_frontend_logs()
