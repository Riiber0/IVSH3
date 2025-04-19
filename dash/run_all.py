import os
import sys
import subprocess
import random
import time

#proc_robustMPC = subprocess.Popen(command_robustMPC, shell=True)


TEST_CASE = None
OUTER_ZONE = None
OUTER_ZONE_SIZE = None
PLAYBACK = None

TEST_LOCATION = "/home/vagrant/workspace/Dash360-sa-ecf/dash/client_scripts/"
PYTHON_RUNNER = "/usr/bin/python3.6"
BASH_RUNNER = "/bin/bash"
SERVER_LOCATION = "/home/vagrant/workspace/Dash360-sa-ecf/dash/"
SERVER = "caddy"
SERVER_CONF_LOCATION = "/home/vagrant/workspace/Dash360-sa-ecf/dash/"
SERVER_CONF = "Caddyfile"

CELL_DELAY = "10"
CELL_UPLINK = "/home/vagrant/workspace/Dash360-sa-ecf/dash/traces_mpshell/"
CELL_DOWNLINK = "/home/vagrant/workspace/Dash360-sa-ecf/dash/traces_mpshell/"

WIFI_DELAY = "50"
WIFI_UPLINK = "/home/vagrant/workspace/Dash360-sa-ecf/dash/traces_mpshell/"
WIFI_DOWNLINK = "/home/vagrant/workspace/Dash360-sa-ecf/dash/traces_mpshell/"

TRACE_HIGH = '/home/vagrant/workspace/Dash360-sa-ecf/dash/traces_mpshell/high/'
TRACE_MEDIUM = '/home/vagrant/workspace/Dash360-sa-ecf/dash/traces_mpshell/medium/'

def trace_selector():
    traces_high = os.listdir('/home/vagrant/workspace/Dash360-sa-ecf/dash/traces_mpshell/high')
    traces_medium = os.listdir('/home/vagrant/workspace/Dash360-sa-ecf/dash/traces_mpshell/medium')

    trace1 = None
    trace2 = None
    while trace1 == trace2:
        trace1 = random.choice(traces_high)
        trace2 = random.choice(traces_medium)

    return trace1,trace2

def server(MP):
    if MP: 
        server_command = [SERVER_LOCATION + SERVER ,"-quic", '-mp',"-conf", SERVER_CONF_LOCATION + SERVER_CONF]
    else:
        server_command = [SERVER_LOCATION + SERVER ,"-quic", "-conf", SERVER_CONF_LOCATION + SERVER_CONF]

    print(server_command)
    return subprocess.Popen(server_command, shell=False)

def client(trace1, rtt1, trace2, rtt2, test_case, outer_zone, outer_zone_size, playback):
    program = [PYTHON_RUNNER, TEST_LOCATION + test_case]

    client_command = ["mpshell", rtt1, trace1, trace1, rtt2, trace2, trace2, BASH_RUNNER, TEST_LOCATION + test_case, outer_zone, outer_zone_size, playback]

    print(client_command)
    return subprocess.run(client_command, shell=False, timeout = 180)

def run_set():
    test_cases = ["mp-ms-br.sh", "mp-ms-nb.sh", "mp-ms-b.sh", "mp-df-nb.sh", "mp-df-b.sh", "sp-df-nb.sh", "sp-df-b.sh"]
    abrs = ['unagi', 'maguro', 'basic', 'sara']
    abrs = ['basic']
    hmd_h_traces = os.listdir('/home/vagrant/workspace/Dash360-sa-ecf/dash/hmd_traces/hmd_high_variance')
    hmd_l_traces = os.listdir('/home/vagrant/workspace/Dash360-sa-ecf/dash/hmd_traces/hmd_low_variance')
    hmd_l_path = '/home/vagrant/workspace/Dash360-sa-ecf/dash/hmd_traces/hmd_low_variance/'
    hmd_h_path = '/home/vagrant/workspace/Dash360-sa-ecf/dash/hmd_traces/hmd_high_variance/'
    last_hmd = 1
    hmd_index = -1

    random.shuffle(hmd_l_traces)
    random.shuffle(hmd_h_traces)

    runs = 0
    total_runs = 5
    while(runs < total_runs):

        random.seed(runs)
        trace1, trace2 = trace_selector()
        rtt1 = trace1.split('_')[1]
        rtt1 = rtt1.split('.')[0]
        rtt2 = trace2.split('_')[1]
        rtt2 = rtt2.split('.')[0]

        for test in test_cases:
            for abr in abrs:

                #DIR = 'exp-' + test.split('.')[0] + abr
                #if not os.path.exists(DIR):
                #    os.mkdir(DIR)

                while True:
                    os.system('sudo systemctl restart systemd-networkd')

                    if test.split('-')[0] == 'mp':
                        server_proc = server(True)
                    else:
                        server_proc = server(False)

                    try:

                        if test.split('-')[0] == 'mp':
                            client_proc = client(TRACE_HIGH+trace1, rtt1, TRACE_MEDIUM+trace2, rtt2, test, 'P', '0', abr)
                        else:
                            client_proc = client(TRACE_HIGH+trace1, rtt1, TRACE_HIGH+trace1, rtt1, test, 'P', '0', abr)

                        if os.path.exists('temp'):
                            os.system('rm temp')
                        else:
                            raise Exception('exit code 1')

                        #command = "mv " + test.split('.')[0] + "-* " + DIR 
                        #os.system(command)

                        server_proc.terminate()
                        break

                    except Exception as e:
                        server_proc.terminate()
                        print(e)
                        os.system("rm " + test.split('.')[0] + "-*")
                        #sys.exit(0)

        runs += 1

def main():

    """
    MP = False
    if "mp" in TEST_CASE:
        MP = True

    trace1, trace2 = trace_selector()

    server_proc = server(MP)

    test_case = sys.argv[1]
    outer_zone = sys.argv[2]
    outer_zone_size = sys.argv[3]
    playback = sys.argv[4]
    client_proc = client(trace1, trace2, test_case, outer_zone, outer_zone_size, playback)

    client_proc.wait()
    server_proc.terminate()
    """

    random.seed(1000)
    run_set()


if __name__ == "__main__":
    main()
