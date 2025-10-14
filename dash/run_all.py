import os
import sys
import subprocess
import random
import time
import datetime

#proc_robustMPC = subprocess.Popen(command_robustMPC, shell=True)

index = 0

TEST_CASE = None
OUTER_ZONE = None
OUTER_ZONE_SIZE = None
PLAYBACK = None

TEST_LOCATION = "/home/vagrant/workspace/Dash360-sa-ecf/dash/client_scripts/"
CLIENT_LOCATION = "/home/vagrant/workspace/Dash360-sa-ecf/astream/dash_client.py"
PYTHON_RUNNER = "/usr/bin/python3.6"
BASH_RUNNER = "/bin/bash"
SERVER_LOCATION = "/home/vagrant/workspace/Dash360-sa-ecf/dash/"
SERVER_DEFAULT = "caddy_df"
SERVER_SA_ECF = "caddy_sa-ecf"
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
#/traces_mpshell/medium/

def trace_selector(past_traces):
    traces_high = os.listdir('/home/vagrant/workspace/Dash360-sa-ecf/dash/traces_mpshell/high')
    traces_medium = os.listdir('/home/vagrant/workspace/Dash360-sa-ecf/dash/traces_mpshell/medium')

    trace1 = None
    trace2 = None
    while trace1 == trace2 and trace1 not in past_traces and trace2 not in past_traces:
        trace1 = random.choice(traces_high)
        trace2 = random.choice(traces_medium)

    return trace1,trace2

def server(MP, s):
    if s == 'ms':
        server = SERVER_SA_ECF
    else:
        server = SERVER_DEFAULT

    if MP: 
        server_command = [SERVER_LOCATION + server ,"-quic", '-mp',"-conf", SERVER_CONF_LOCATION + SERVER_CONF]
    else:
        server_command = [SERVER_LOCATION + server ,"-quic", "-conf", SERVER_CONF_LOCATION + SERVER_CONF]

    print(server_command)
    return subprocess.Popen(server_command, shell=False)

def client(trace1, rtt1, trace2, rtt2, p, s, m, t, b):
    client_command = ["mpshell", rtt1, trace1, trace1, rtt2, trace2, trace2, PYTHON_RUNNER, CLIENT_LOCATION, '-m', 'https://10.0.2.15:4242/dash_tiled.mpd', '-q', '-tr', 'PERFPREDICT', '-tg', '-p', 'unagi', '-pt', t, '-bm', b]
    
    if p == 'mp':
        client_command.append('-mp')
    if s == 'ms':
        client_command.append('-ms')

    client_command.append('-tp')
    if m == 'b':
        client_command.append('uni')
    if m == 'exp':
        client_command.append('group')
    if m == 'nb':
        client_command.append('line')

    if b != '0':
        client_command.append('-sm')
        client_command.append('200')

    date = datetime.datetime.now()
    filename = p + '-' + s + '-' + m + '-' + 'VP' + '_'+ index + '_' + t.replace('.', '') + '_' + b + '_' + date.strftime("%H-%M-%S_%d-%m-%y")+'.txt'
    log = open(filename, 'w')

    print(client_command)
    return subprocess.run(client_command, shell=False, stdout = log, timeout = 300), log

def run_set():
    past_traces = []
    test_cases = ["mp-ms-nb"]
    abrs = ['unagi']
    times = ['2.0']
    max_buffer = ["0"]#, "1", "2"]
    hmd_h_traces = os.listdir('/home/vagrant/workspace/Dash360-sa-ecf/dash/hmd_traces/hmd_high_variance')
    hmd_l_traces = os.listdir('/home/vagrant/workspace/Dash360-sa-ecf/dash/hmd_traces/hmd_low_variance')
    hmd_l_path = '/home/vagrant/workspace/Dash360-sa-ecf/dash/hmd_traces/hmd_low_variance/'
    hmd_h_path = '/home/vagrant/workspace/Dash360-sa-ecf/dash/hmd_traces/hmd_high_variance/'
    last_hmd = 1
    hmd_index = -1

    random.shuffle(hmd_l_traces)
    random.shuffle(hmd_h_traces)

    runs = 3

    for i in range(0, runs):
        trace1, trace2 = trace_selector(past_traces)
        past_traces.append(trace1)
        past_traces.append(trace2)

    global index
    total_runs = 10
    #t = "1.5"
    while(runs < total_runs):
        index = str(runs)

        random.seed(runs)
        trace1, trace2 = trace_selector(past_traces)
        past_traces.append(trace1)
        past_traces.append(trace2)
        #print(trace1)
        #sys.exit(0)
        rtt1 = trace1.split('_')[2]
        rtt1 = rtt1.split('.')[0]
        rtt1 = str(int(rtt1)/2)
        rtt1 = rtt1.split('.')[0]
        rtt2 = trace2.split('_')[2]
        rtt2 = rtt2.split('.')[0]
        rtt2 = str(int(rtt2)/2)
        rtt2 = rtt2.split('.')[0]

        for test in test_cases:
            p = test.split('-')[0]
            s = test.split('-')[1]
            m = test.split('-')[2]
            for t in times:
                for b in max_buffer:

                    #DIR = 'exp-' + test.split('.')[0] + abr
                    #if not os.path.exists(DIR):
                    #    os.mkdir(DIR)

                    while True:
                        os.system("ip link show | grep cw | awk -F : '{print $2}' | tr -d ' ' | while read b; do sudo ip link set $b down; done")

                        if test.split('-')[0] == 'mp':
                            server_proc = server(True, s)
                        else:
                            server_proc = server(False, s)

                        try:

                            if test.split('-')[0] == 'mp':
                                client_proc, log = client(TRACE_HIGH+trace1, rtt1, TRACE_MEDIUM+trace2, rtt2, p, s, m, t, b)
                            else:
                                client_proc, log = client(TRACE_HIGH+trace1, rtt1, TRACE_HIGH+trace1, rtt1, p, s, m, t, b)

                            log.close()
                            if os.path.exists('temp'):
                                os.system('rm temp')
                            else:
                                raise Exception('exit code 1')

                            command = "sudo mv " + log.name + " exp"
                            print(command)
                            os.system(command)

                            server_proc.terminate()
                            break

                        except Exception as e:
                            os.system("pkill python3.6")
                            server_proc.terminate()
                            print(e)
                            command = "sudo rm " + p + '-*'
                            print(command)
                            os.system(command)
                            #sys.exit(0)

        os.system('rm completed_*')
        os.system(f'touch completed_{runs}')
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
