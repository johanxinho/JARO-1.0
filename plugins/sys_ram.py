import subprocess
def run(payload):
    out = subprocess.check_output(["free", "-m"], text=True)
    return "Estado actual de RAM (MB):\n" + out
