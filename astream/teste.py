import io
import read_mpd
from configure_log_file import configure_log_file
from collections import defaultdict
import conn as glueConnection
import subprocess
import time
import sys
import timeit
import os

mp = None
ms = None

if len(sys.argv) > 1:
    mp = True

if len(sys.argv) > 2:
    ms = True

glueConnection.setupLib(ms)
glueConnection.setupPM(True, mp, ms, False, 'lowRTT', 'olia')
glueConnection.connectPM()

segment_url = 'https://10.0.2.15:4242/bulk_file'

print('downloading')

start_time = timeit.default_timer()

if ms:
    segment_size = glueConnection.download_segment_priority_PM(segment_url, 0xff)
else:
    segment_size = glueConnection.download_segment_PM(segment_url)

download_time = timeit.default_timer() - start_time

print(f'downloaded size: {segment_size}, in {download_time}')

os.system('touch /home/vagrant/workspace/Dash360-sa-ecf/dash/test_temp')
