import os
import sys
import subprocess

#proc_robustMPC = subprocess.Popen(command_robustMPC, shell=True)


TESTE_CASE = sys.argv[1]
TESTL_LOCATION = "/home/vagrant/workspace/Dash360-sa-ecf/astream/scripts/"
PYTHON_RUNNER = "/usr/bin/python3.6"
SERVER_LOCATION = "/home/vagrant/workspace/Dash360-sa-ecf/dash/"
SERVER = "caddy"
SERVER_CONF_LOCATION = "/home/vagrant/workspace/Dash360-sa-ecf/dash/"
SERVER_CONF = "CaddtFile"

def server():
    server_command = SERVER_LOCATION + SERVER +  " -quic -mp -conf " + SERVER_CONF_LOCATION + SERVER_CONF
    subprocess.Popen(server_command, shell=FALSE)

def client():

def main():
    


if __name__ == "__main__":
    main()
