import subprocess
import os
try:
    out = subprocess.check_output(["lsof", "-t", "-i:9119"]).decode().strip()
    if out:
        for pid in out.split('\n'):
            print(f"Killing PID {pid}")
            os.system(f"kill -9 {pid}")
    else:
        print("No process found on 9119")
except Exception as e:
    print(e)
