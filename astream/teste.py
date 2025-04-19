import io
import read_mpd
from configure_log_file import configure_log_file
from collections import defaultdict
import conn as glueConnection
import subprocess


glueConnection.setupLib(False)
glueConnection.setupPM(True, True, False, False, 'lowRTT', 'olia')

segment_url = 'https://10.0.2.15:4242/bulk_file'

print('command')

#subprocess.run(['sudo', 'bash', '/home/vagrant/workspace/Dash360-sa-ecf/astream/setup_wifi_route.sh'])
#subprocess.run(["cat", "/etc/iproute2/rt_tables"])

print('ip route show table local')
subprocess.run(['ip', 'route', 'show', 'table', 'local'])
print('ip route show table main')
subprocess.run(['ip', 'route', 'show', 'table', 'main'])
print('defalt')
subprocess.run(['ip', 'route', 'show', 'table', 'default'])
print('unspec')
subprocess.run(['ip', 'route', 'show', 'table', 'unspec'])

subprocess.run(['traceroute', '10.0.2.15'])
segment_size = glueConnection.download_segment_PM(segment_url)

subprocess.run(['ifconfig'])
