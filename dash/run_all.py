import os
import sys
import subprocess

#proc_robustMPC = subprocess.Popen(command_robustMPC, shell=True)


TEST_CASE = sys.argv[1]
TEST_LOCATION = "/home/vagrant/workspace/Dash360-sa-ecf/astream/scripts/"
PLAYBACK = sys.argv[2]
PYTHON_RUNNER = "/usr/bin/python3.6"
BASH_RUNNER = "/bin/bash"
SERVER_LOCATION = "/home/vagrant/workspace/Dash360-sa-ecf/dash/"
SERVER = "caddy"
SERVER_CONF_LOCATION = "/home/vagrant/workspace/Dash360-sa-ecf/dash/"
SERVER_CONF = "Caddyfile"

CELL_DELAY = "10"
CELL_UPLINK = "/home/vagrant/workspace/Dash360-sa-ecf/dash/traces_mpshell/12Mbps_mocktrace"
CELL_DOWNLINK = "/home/vagrant/workspace/Dash360-sa-ecf/dash/traces_mpshell/12Mbps_mocktrace"

WIFI_DELAY = "10"
WIFI_UPLINK = "/home/vagrant/workspace/Dash360-sa-ecf/dash/traces_mpshell/12Mbps_mocktrace"
WIFI_DOWNLINK = "/home/vagrant/workspace/Dash360-sa-ecf/dash/traces_mpshell/12Mbps_mocktrace"


def server(MP):
    MP_string = ""
    if MP:
        MP_string = "-mp"

    server_command = [SERVER_LOCATION + SERVER ,"-quic", MP_string,"-conf", SERVER_CONF_LOCATION + SERVER_CONF]

    print(server_command)
    return subprocess.Popen(server_command, shell=False)

def client():
    program = [PYTHON_RUNNER, TEST_LOCATION + TEST_CASE]
    client_command = ["mpshell", CELL_DELAY, CELL_UPLINK, CELL_DOWNLINK, WIFI_DELAY, WIFI_UPLINK, WIFI_DOWNLINK, BASH_RUNNER, TEST_LOCATION + TEST_CASE, PLAYBACK]

    print(client_command)
    return subprocess.Popen(client_command, shell=False)

def main():
    MP = False
    if "mp" in TEST_CASE:
        MP = True

    server_proc = server(MP)
    client_proc = client()

    client_proc.wait()
    server_proc.terminate()

if __name__ == "__main__":
    main()
