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
            "curl -s -X POST http://127.0.0.1:8000/api/data/sync"
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
