import subprocess
import os

def subprocess_cmd(command):
    print ('executing:')
    print (command)

    process = subprocess.Popen(command,stdout=subprocess.PIPE, shell=True)
    proc_stdout = process.communicate()[0].strip()
    print (proc_stdout.decode("utf-8"))

def start_server():
    subprocess_cmd(
            'gunicorn --timeout 600 --workers=3 --bind=0.0.0.0:5000 app:app'
            )
    return

subprocess_cmd('python --version')
subprocess_cmd('pip --version')
start_server()
