#!/usr/local/bin/python
"""
Author:            Parikshit Juluri
Contact:           pjuluri@umkc.edu
Testing:
    import dash_client
    mpd_file = <MPD_FILE>
    dash_client.playback_duration(mpd_file, 'http://198.248.242.16:8005/')

    From commandline:
    python dash_client.py -m "http://198.248.242.16:8006/media/mpd/x4ukwHdACDw.mpd" -p "all"
    python dash_client.py -m "http://127.0.0.1:8000/media/mpd/x4ukwHdACDw.mpd" -p "basic"

"""

import conn as glueConnection
import read_mpd
import urllib.parse
import urllib.request, urllib.error, urllib.parse
import random
import os
import sys
import errno
import ssl
import timeit
import http.client
import io
import math
import json
import struct
import subprocess
import socket
from string import ascii_letters, digits
from argparse import ArgumentParser
from multiprocessing import Process, Queue
from collections import defaultdict, deque
from adaptation import basic_dash, basic_dash2, weighted_dash, netflix_dash
from adaptation import basic_dash3
from adaptation.adaptation import WeightedMean
from configure_log_file import configure_log_file, write_json
import config_dash
import dash_buffer
import time
import pandas as pd
from tile_delivery import *
from priority_manager import GroupPriority, UniPriority
from threading import Thread, Lock, BoundedSemaphore
from util import linePriority, outer_zone_percentage, outer_zone_fixed

# Constants
DEFAULT_PLAYBACK = 'BASIC'
DOWNLOAD_CHUNK = 1024

# Globals for arg parser with the default values
# Not sure if this is the correct way ....
MPD = None
LIST = False
PLAYBACK = DEFAULT_PLAYBACK
DOWNLOAD = False
SEGMENT_LIMIT = None

HEAD_TRACE_PATH = "/home/vagrant/workspace/Dash360-sa-ecf/astream/"
CLIENT = ''

#streams globals
#old (maibe remove)
limiter = BoundedSemaphore(100)

#Globals chunks
chunk_lock = Lock()
chunk_start_size = 0
chunk_start_time = 0
chunk_end_size = 0
chunk_end_time = 0
chunk_tiles = 0
active_streams = 0
WARMUP_TIME = 3

class DashPlayback:
    """
    Audio[bandwidth] : {duration, url_list}
    Video[bandwidth] : {duration, url_list}
    """
    def __init__(self):

        self.min_buffer_time = None
        self.playback_duration = None
        self.audio = dict()
        self.video = dict()
        self.ssims = dict()


def get_mpd(url):
    """ Module to download the MPD from the URL and save it to file"""
    print(url)
    try:
        if url.find('https://') == 0:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            connection = urllib.request.urlopen(url, timeout=10, context=ctx)
        else:
            connection = urllib.request.urlopen(url, timeout=10)
    except urllib.error.HTTPError as error:
        config_dash.LOG.error("Unable to download MPD file HTTP Error: %s" % error.code)
        return None
    except urllib.error.URLError as error:
        error_message = "URLError. Unable to reach Server.Check if Server active"
        config_dash.LOG.error(error_message)
        print(error,"\n",error_message)
        return None
    except IOError as xxx_todo_changeme:
        http.client.HTTPException = xxx_todo_changeme
        message = "Unable to , file_identifierdownload MPD file HTTP Error."
        config_dash.LOG.error(message)
        return None
    
    mpd_data = connection.read()
    connection.close()
    config_dash.LOG.info("Downloaded the MPD file")
    return io.BytesIO(mpd_data)


def get_bandwidth(data, duration):
    """ Module to determine the bandwidth for a segment
    download"""
    return data * 8/duration


def get_domain_name(url):
    """ Module to obtain the domain name from the URL
        From : http://stackoverflow.com/questions/9626535/get-domain-name-from-url
    """
    parsed_uri = urllib.parse.urlparse(url)
    domain = '{uri.scheme}://{uri.netloc}/'.format(uri=parsed_uri)
    return domain


def id_generator(id_size=6):
    """ Module to create a random string with uppercase 
        and digits.
    """
    return 'TEMP_' + ''.join(random.choice(ascii_letters+digits) for _ in range(id_size))

def gelato_get_action(conn, env_info):
    data = json.dumps(env_info)
    data = data.encode('utf-8')
    json_len = struct.pack("!H", len(data))

    conn.sendall(json_len + data)

    data_rv_len_struct = conn.recv(2, socket.MSG_WAITALL)
    data_rv_len, *_ = struct.unpack("!H", data_rv_len_struct)
    data_rv_data = conn.recv(data_rv_len, socket.MSG_WAITALL)
    data_rv = json.loads(data_rv_data)
    action = data_rv['action']

    return action

def gelato_close(conn):
    d = {'close':True}
    data = json.dumps(d)
    data = data.encode('utf-8')
    json_len = struct.pack("!H", len(data))
    conn.sendall(json_len + data)

def update_chunk():
    global chunk_tiles
    global active_streams
    global chunk_end_time
    global chunk_end_size

    chunk_lock.acquire()
    chunk_tiles += 1
    active_streams -= 1
    config_dash.LOG.info('Current Batch: tiles = {}'.format(chunk_tiles))

    if active_streams == 0:
        chunk_end_size = glueConnection.GetBytes(CLIENT)
        chunk_end_time = timeit.default_timer()

        chunk_size = chunk_end_size - chunk_start_size
        chunk_time = chunk_end_time - chunk_start_time

        config_dash.LOG.info('Last Batch: {}. Size = {}, time {}'.format(chunk_tiles, chunk_size, str(chunk_time)))
        chunk_tiles = 0

    chunk_lock.release()

def start_chunk(start_time, tiles):
    chunk_lock.acquire()
    global chunk_start_size
    global chunk_start_time
    global chunk_tiles
    global active_streams
    global chunk_end_size
    global chunk_end_time

    active_streams += tiles

    chunk_end_size = glueConnection.GetBytes(CLIENT)
    chunk_end_time = timeit.default_timer()

    chunk_size = chunk_end_size - chunk_start_size
    chunk_time = chunk_end_time - chunk_start_time

    if chunk_size > 0 and chunk_time > 0:
        chunk_time = chunk_end_time - chunk_start_time

        config_dash.LOG.info('Last Batch: {}. Size = {}, time {}'.format(chunk_tiles, chunk_size, str(chunk_time)))

    chunk_tiles = 0
    chunk_start_time = timeit.default_timer()
    config_dash.LOG.info('New Batch. time = {}'.format(str(chunk_start_time)))
    chunk_lock.release()

def download_segment(segment_url, dash_folder, download=False):
    """ Module to download the segment with one
        permanent HTTP connection.
        File is not written to disk.
    """
    cropped_fInd = segment_url.rfind('/')
    segment_name = segment_url[cropped_fInd+1:len(segment_url)]

    filename = ""
    if download:
        filename = os.path.join(dash_folder, segment_name)
        print("SAVING IN ", filename)

    segment_size = glueConnection.download_segment_PM(segment_url)
    if segment_size < 0:
        config_dash.JSON_HANDLE['playback_info']['connection_loss'] += 1
        raise ValueError("invalid segment_size, connection dropped")
    return segment_size, segment_name

def download_segment_priority(segment_url, priority, dash_folder, download=False):
    """ Module to download the segment with one
        permanent HTTP connection.
        File is not written to disk.
    """
    cropped_fInd = segment_url.rfind('/')
    segment_name = segment_url[cropped_fInd+1:len(segment_url)]

    filename = ""
    if download:
        filename = os.path.join(dash_folder, segment_name)
        print("SAVING IN ", filename)

    segment_size = glueConnection.download_segment_priority_PM(segment_url, priority)
    if segment_size < 0:
        config_dash.JSON_HANDLE['playback_info']['connection_loss'] += 1
        #raise ValueError("invalid segment_size, connection dropped")
        config_dash.LOG.info("Invalid segment size: {}".format(segment_size))
        os._exit(0)

    return segment_size, segment_name

def download_thread(playback_type, tile, segment_url, priority, file_identifier, download,
                    previous_download_times, tiles_in_segment, download_sizes_t, segment_files, priority_m):

    priority_m.lock_priority(priority)

    config_dash.LOG.info("{}: Downloading file {}".format(playback_type.upper(), segment_url))
    
    try:
        start_time = timeit.default_timer()

        if MS:
            segment_size, segment_filename = download_segment_priority(segment_url, priority, file_identifier, download)
        else:
            segment_size, segment_filename = download_segment(segment_url, file_identifier, download)

        end_time = timeit.default_timer()
        segment_download_time = end_time - start_time
        previous_download_times.append(segment_download_time)
        #config_dash.LOG.info("{}: Downloaded segment {}".format(playback_type.upper(), segment_url))
    except IOError as e:
        config_dash.LOG.error('Unable to save segment %s' % e)
        os._exit(1)

    tiles_in_segment.append(tile)
    priority_m.update_priorities(priority)
    update_chunk()
    #segment_size = dp_object.video[current_bitrate].segment_size

    download_sizes_t.append(segment_size)
    segment_files.append(segment_filename)

    #update tje JSON information
    segment_name = os.path.split(segment_url)[1]
    if 'segment_info' not in config_dash.JSON_HANDLE:
        config_dash.JSON_HANDLE['segment_info'] = list()
    config_dash.JSON_HANDLE['segment_info'].append((segment_name, segment_size, segment_download_time))

    download_sizes_t.append(segment_size)

    config_dash.LOG.info('Downloaded {}. Size = {} in {} seconds'.format( segment_url, segment_size, str(segment_download_time)))

def get_media_all(domain, media_info, file_identifier, done_queue):
    """ Download the media from the list of URL's in media
    """
    bandwidth, media_dict = media_info
    media = media_dict[bandwidth]
    media_start_time = timeit.default_timer()
    for segment in [media.initialization] + media.url_list:
        start_time = timeit.default_timer()
        segment_url = urllib.parse.urljoin(domain, segment)
        _, segment_file = download_segment(segment_url, file_identifier)
        elapsed = timeit.default_timer() - start_time
        if segment_file:
            done_queue.put((bandwidth, segment_url, elapsed))
    media_download_time = timeit.default_timer() - media_start_time
    done_queue.put((bandwidth, 'STOP', media_download_time))
    return None


def make_sure_path_exists(path):
    """ Module to make sure the path exists if not create it
    """
    try:
        os.makedirs(path)
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise


def print_representations(dp_object):
    """ Module to print the representations"""
    print("The DASH media has the following video representations/bitrates")
    for bandwidth in dp_object.video:
        print(bandwidth)

def get_segment_tile_buffer(segment_number, dash_player):
    segment = dash_player.get_segment(segment_number)

    if segment != None:
        return segment['tiles_in_segment']

    return []

def get_segment_bitrate(segment_number, dash_player):
    segment = dash_player.get_segment(segment_number)
    
    return segment['bitrate']

def get_player_segment_number(dash_player):
    segment= dash_player.current_segment
    
    if segment == None:
        return -1

    else:
        return segment['segment_number']

def check_segment_in_buffer(segment_number, dash_player):
    segment = dash_player.get_segment(segment_number)

    if segment == None:
        return False
    
    return True

def start_playback_smart(dp_object, domain, playback_type=None, download=False, video_segment_duration=None):
    """ Module that downloads the MPD-FIle and download
        all the representations of the Module to download
        the MPEG-DASH media.
        Example: start_playback_smart(dp_object, domain, "SMART", DOWNLOAD, video_segment_duration)

        :param dp_object:       The DASH-playback object
        :param domain:          The domain name of the server (The segment URLS are domain + relative_address)
        :param playback_type:   The type of playback
                                1. 'BASIC' - The basic adapataion scheme
                                2. 'SMART' - Segment Aware Rate Adaptation
                                3. 'NETFLIX' - Buffer based adaptation used by Netflix
        :param download: Set to True if the segments are to be stored locally (Boolean). Default False
        :param video_segment_duration: Playback duratoin of each segment
        :return:
    """
    glueConnection.startLogging(1000)
    # Initialize the DASH buffer
    dash_player = dash_buffer.DashPlayer(dp_object.playback_duration, video_segment_duration, TP)
    dash_player.start()
    config_dash.LOG.info('Video Duration is %i' % dp_object.playback_duration)
    # A folder to save the segments in
    file_identifier = id_generator()
    if download:
        os.makedirs(file_identifier)
        config_dash.LOG.info("The segments are stored in %s" % file_identifier)

    dp_list = dict()
    downloaded_tiles = dict()

    for bitrate in dp_object.video:
        # Getting the URL list for each bitrate
        dp_object.video[bitrate] = read_mpd.get_url_list(dp_object.video[bitrate], video_segment_duration,
                                                         dp_object.playback_duration, bitrate)

        for tile_id in dp_object.video[bitrate].url_list:
            media_urls = dp_object.video[bitrate].url_list[tile_id]

            for segment_count, segment_url in enumerate(media_urls, dp_object.video[bitrate].start):
                if segment_count not in dp_list.keys():
                    dp_list[segment_count] = dict()
                    downloaded_tiles[segment_count] = dict()

                if bitrate not in dp_list[segment_count].keys():
                    dp_list[segment_count][bitrate] = dict()
                    downloaded_tiles[segment_count][bitrate] = dict()

                dp_list[segment_count][bitrate][tile_id] = segment_url
                downloaded_tiles[segment_count][bitrate][tile_id] = False

    bitrates = list(dp_object.video.keys())
    bitrates.sort()

    ssims = dp_object.ssims
    ssim_list = [list(ssim.values()) for ssim in ssims.values()]

    for segment in ssims.keys():
        b = list(ssims[segment])
        b.sort()
        for i in range(0, len(bitrates)):
            ssims[segment][bitrates[i]] = ssims[segment][b[i]]

    sizes = list()
    for bitrate in dp_list[segment_count]:
        sizes.append((dp_object.video[bitrate].segment_size*8)/(1024*1024)*60)

    bitrates = list(dp_object.video.keys())
    bitrates.sort()
    average_dwn_time = 0
    segment_files = []
    # For basic adaptation
    weighted_mean_object = None
    current_bitrate = bitrates[0]
    previous_bitrate = None
    total_downloaded = 0
    # Delay in terms of the number of segments
    delay = 0
    segment_duration = dp_object.video[current_bitrate].segment_duration
    segment_size = segment_download_time = None
    # Netflix Variables
    average_segment_sizes = netflix_rate_map = None
    netflix_state = "INITIAL"
    # tile variables
    recent_download_sizes = []
    previous_download_times = []
    total_tiles = len(dp_list[segment_count][bitrate])
    tiles = dict()
    tiles_in_segment = []
    pre_ulrs_dict = None # (tile : [bitrate, stream_priotyt]), created by ABR
    urls_dict = None # (file_url : stream_prioryt), created after pre_url_dict mapping
    emergency_flag = False
    # segment variables
    previous_segments_times = []
    total_segment_size = None
    previous_segments_sizes = []
    last_segment = -1
    new_segment = False
    #tread variables
    threads = []
    download_sizes_t = []
    download_times_t = []
    #buffer varialbes
    segment_increase = 0
    #batch variables
    global CLIENT
    CLIENT = urllib.parse.urlparse(domain).netloc
    #gelato variables
    conn = None
    addr =None
    gelato_p = None
    gelato_data = {
            'buffer': 0,
            'cum_rebuf': 0,
            'sizes': [sizes for i in range(0, 5)],
            'ssims': ssim_list[0:5],
            'channel_name': 'AStream360'
    }
    print('gelato data sizes" {}'.format(gelato_data['sizes']))

    # tile reader
    if TILE_READER == "NARROW":
        tileReader = NarrowReader(dash_player.playback_timer, HEAD_TRACE_PATH+'move_alert.csv', segment_duration)
    elif TILE_READER == "ALL":
        tileReader = AllReader(dash_player.playback_timer, total_tiles, segment_duration)
    elif TILE_READER.upper() == "PERFPREDICT":
        tileReader = PerfPredict(dash_player.playback_timer, HEAD_TRACE_PATH+'move_alert.csv', segment_duration, float(PREDICT_TIME))

    #tile getter
    if TILE_GETTER or TILE_READER == "PERFPREDICT":
        dash_player.tile_getter = NarrowReader(dash_player.playback_timer, HEAD_TRACE_PATH+'move_alert.csv', segment_duration)
        dash_player.tile_getter.start()
    else:
        dash_player.tile_getter = tileReader

    tileReader.start()

    #priority manager
    if TP.upper() == "GROUP":
        priority_m = GroupPriority(int(MAX_BUFFER_SIZE) + 1, int(STREAM_MAX))
    elif TP.upper() == "UNI":
        priority_m = UniPriority(int(STREAM_MAX))

    #outer zone
    if OUTER_ZONE == "P":
        outer_zone_func = outer_zone_percentage

    elif OUTER_ZONE == "F":
        outer_zone_func = outer_zone_fixed

    #gelato setup
    if playback_type.upper() == 'MAGURO':
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        if os.path.exists("/tmp/socket_test.s"):
          os.remove("/tmp/socket_test.s")

        sock.bind("/tmp/socket_test.s")
        gelato_p = subprocess.Popen(['python3', '/home/vagrant/workspace/Dash360-sa-ecf/astream/adaptation/abr_rl_test/test.py', 'maguro' ,'/home/vagrant/workspace/Dash360-sa-ecf/astream/adaptation/abr_rl_test/models/maguro_model.pt', '/tmp/socket_test.s'])
        sock.listen()
        conn, addr = sock.accept()
    elif playback_type.upper() == 'UNAGI':
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        if os.path.exists("/tmp/socket_test.s"):
          os.remove("/tmp/socket_test.s")

        sock.bind("/tmp/socket_test.s")
        gelato_p = subprocess.Popen(['python3', '/home/vagrant/workspace/Dash360-sa-ecf/astream/adaptation/abr_rl_test/test.py', 'maguro' ,'/home/vagrant/workspace/Dash360-sa-ecf/astream/adaptation/abr_rl_test/models/unagi_model.pt', '/tmp/socket_test.s'])
        sock.listen()
        conn, addr = sock.accept()

    # waiting for the player to finish playing
    segment_number = dp_object.video[current_bitrate].start
    download_flag = False
    warmup = False
    while dash_player.playback_state not in dash_buffer.EXIT_STATES:
        segment_number, reading_dict = tileReader.get_tiles()
        if segment_number <= len(dp_list.keys()):

            if dash_player.current_segment != None and len(dash_player.emergency_tiles) > 0:
                segment_number = get_player_segment_number(dash_player)
                tiles_l = dash_player.emergency_tiles
                tiles = {tile:255 for tile in tiles_l}
                config_dash.LOG.info("emergency call: segment {} total {} tiles{}".format(segment_number, len(tiles), tiles))
                current_bitrate = dash_player.current_segment['bitrate']
                tiles_in_segment = dash_player.current_segment['tiles_in_segment'] 
                emergency_flag = True

            else:
                
                n_tiles = list(reading_dict.keys())
                tiles_in_segment = get_segment_tile_buffer(segment_number, dash_player) 
                new_tiles = [tile for tile in n_tiles if tile not in tiles_in_segment]

                if segment_number == get_player_segment_number(dash_player):
                    if new_tiles == []:
                        next_segment = segment_number + segment_increase + 1
                        if segment_increase + 1 < int(MAX_BUFFER_SIZE):
                            segment_increase += 1

                        if segment_number + segment_increase < len(dp_list.keys()):
                            segment_number += segment_increase
                        tiles_in_segment = get_segment_tile_buffer(segment_number, dash_player) 
                        new_tiles = [tile for tile in n_tiles if tile not in tiles_in_segment]

                    else:
                        segment_increase = 0

                if not check_segment_in_buffer(segment_number, dash_player):
                    new_segment = True
                    segment_increase = 0

                #Unstable
                #tiles = tiles_in_segment.copy()
                #tiles += new_tiles
                #tiles.sort()

                #Bitrate selection
                if BITRATE is not None:
                    pass

                elif not new_segment:
                    current_bitrate = get_segment_bitrate(segment_number, dash_player)

                elif playback_type.upper() == "BASIC":
                    current_bitrate, average_dwn_time = basic_dash3.basic_dash3(
                    segment_number, bitrates, average_dwn_time, previous_segments_sizes, 
                    previous_segments_times, current_bitrate)

                elif playback_type.upper() == 'SMART':
                    if not weighted_mean_object:
                        weighted_mean_object = WeightedMean(config_dash.SARA_SAMPLE_COUNT)
                        config_dash.LOG.debug("Initializing the weighted Mean object")

                    current_bitrate, delay = weighted_dash.weighted_dash(bitrates, dash_player, 
                            weighted_mean_object.weighted_mean_rate, 
                                current_bitrate, get_segment_sizes(dp_object, segment_number))

                elif playback_type.upper() == 'MAGURO' or playback_type.upper() == 'UNAGI':
                    action = gelato_get_action(conn, gelato_data)
                    current_bitrate = bitrates[action]
                    
                if len(new_tiles) == 0:
                    continue

                #priority selection
                tiles = dict()
                tiles = {tile:reading_dict[tile] for tile in new_tiles}

                tiles = priority_m.get_priority(tiles, segment_increase)
                #print(tiles)

            if len(tiles) > 0:
                glueConnection.connectPM()
            else:
                continue

            total_segment_size = 0
            for tile in tiles:
                if downloaded_tiles[segment_number][bitrate][tile]:
                    continue

                download_flag = True
                bitrate = current_bitrate
                priority = tiles[tile]
                # print("{} {} {}".format(segment_number, bitrate, tile))

                path_to_tiles = dp_list[segment_number][bitrate]
                segment_url = urllib.parse.urljoin(domain, path_to_tiles[tile])

                t = Thread(target=download_thread, daemon=True,
                            args=(playback_type, tile, segment_url, priority, file_identifier, download, 
                                previous_download_times, tiles_in_segment, recent_download_sizes, segment_files, priority_m))

                threads.append(t)

                downloaded_tiles[segment_number][bitrate][tile] = True

            if download_flag:
                start_time = timeit.default_timer()
                start_chunk(start_time, len(threads))
                for t in threads:
                    t.start()

                if warmup:
                    t.join()

                if new_segment:
                    segment_info = {'playback_length' : video_segment_duration,
                                    'bitrate' : current_bitrate,
                                    'ssim' : ssims[segment_number][current_bitrate],
                                    'segment_number' : segment_number,
                                    'tiles_in_segment' : tiles_in_segment}

                    dash_player.write(segment_info)

                threads = []

            if playback_type.upper() == 'SMART' and weighted_mean_object and new_segment:
                #print(get_segment_sizes(dp_object, segment_number))
                weighted_mean_object.update_weighted_mean(get_segment_sizes(dp_object, segment_number)[current_bitrate], last_chunk_time)

            elif playback_type.upper() == 'MAGURO' or playback_type.upper() == 'UNAGI' and new_segment:
                gelato_flag = True
                gelato_data['buffer'] = dash_player.get_buffer_length()
                gelato_data['cum_rebuf'] = dash_player.get_rebuf()
                gelato_data['past_chunk'] = {
                            'delay': chunk_end_time - chunk_start_time,
                            'ssim': ssims[segment_number][bitrate],
                            'size': ((chunk_end_size - chunk_start_size)*8)/(1024*1024)
                }
                l = ssim_list[int(segment_number):int(segment_number)+5]
                if len(l) < 5 and len(l) > 0:
                    l = l + [l[-1] for i in range(0, 5-len(l))]

                gelato_data['ssims'] = l

            if download_flag:
            #    config_dash.LOG.info("{} : The total downloaded = {}, segment_size = {}, segment_number = {}".format(
            #                        playback_type.upper(), total_downloaded, segment_size, segment_number))
                download_flag = False
                #if NO_KEEP_ALIVE:
                    #print('no keep alive')
                    #glueConnection.closeConnection()

            if emergency_flag:
                emergency_flag = False
                last_segment = segment_number
                dash_player.emergency_tiles = []
                dash_player.current_segment['tiles_in_segment'].extend(list(tiles))

            if segment_number > WARMUP_TIME and warmup == True:
                warmup = False
                config_dash.LOG.info("{} : Warmup finished".format(playback_type.upper()))

        if previous_bitrate:
            if previous_bitrate < current_bitrate:
                config_dash.JSON_HANDLE['playback_info']['up_shifts'] += 1
            elif previous_bitrate > current_bitrate:
                config_dash.JSON_HANDLE['playback_info']['down_shifts'] += 1

            previous_bitrate = current_bitrate

        last_segment = segment_number
        new_segment = False


    #if playback_type.upper() == 'GELATO':
    #   gelato_close(conn)
    glueConnection.stopLogging()
    glueConnection.closeConnection()

    if not download:
        clean_files(file_identifier)

def start_playback_smart_sequential(dp_object, domain, playback_type=None, download=False, video_segment_duration=None):
    """ Module that downloads the MPD-FIle and download
        all the representations of the Module to download
        the MPEG-DASH media.
        Example: start_playback_smart(dp_object, domain, "SMART", DOWNLOAD, video_segment_duration)

        :param dp_object:       The DASH-playback object
        :param domain:          The domain name of the server (The segment URLS are domain + relative_address)
        :param playback_type:   The type of playback
                                1. 'BASIC' - The basic adapataion scheme
                                2. 'SMART' - Segment Aware Rate Adaptation
                                3. 'NETFLIX' - Buffer based adaptation used by Netflix
        :param download: Set to True if the segments are to be stored locally (Boolean). Default False
        :param video_segment_duration: Playback duratoin of each segment
        :return:
    """
    glueConnection.startLogging(1000)
    # Initialize the DASH buffer
    dash_player = dash_buffer.DashPlayer(dp_object.playback_duration, video_segment_duration, TP)
    dash_player.start()
    print(dp_object.playback_duration)
    # A folder to save the segments in
    file_identifier = id_generator()
    if download:
        os.makedirs(file_identifier)
        config_dash.LOG.info("The segments are stored in %s" % file_identifier)

    dp_list = dict()
    downloaded_tiles = dict()

    for bitrate in dp_object.video:
        # Getting the URL list for each bitrate
        dp_object.video[bitrate] = read_mpd.get_url_list(dp_object.video[bitrate], video_segment_duration,
                                                         dp_object.playback_duration, bitrate)

        for tile_id in dp_object.video[bitrate].url_list:
            media_urls = dp_object.video[bitrate].url_list[tile_id]

            for segment_count, segment_url in enumerate(media_urls, dp_object.video[bitrate].start):
                if segment_count not in dp_list.keys():
                    dp_list[segment_count] = dict()
                    downloaded_tiles[segment_count] = dict()

                if bitrate not in dp_list[segment_count].keys():
                    dp_list[segment_count][bitrate] = dict()
                    downloaded_tiles[segment_count][bitrate] = dict()

                dp_list[segment_count][bitrate][tile_id] = segment_url
                downloaded_tiles[segment_count][bitrate][tile_id] = False

    bitrates = list(dp_object.video.keys())
    bitrates.sort()
    print(bitrates)
    average_dwn_time = 0
    segment_files = []
    # For basic adaptation
    previous_segment_times = []
    recent_download_sizes = []
    weighted_mean_object = None
    current_bitrate = bitrates[0]
    previous_bitrate = None
    total_downloaded = 0
    # Delay in terms of the number of segments
    delay = 0
    segment_duration = dp_object.video[current_bitrate].segment_duration
    segment_size = segment_download_time = None
    # Netflix Variables
    average_segment_sizes = netflix_rate_map = None
    netflix_state = "INITIAL"
    # tile variables
    total_tiles = len(dp_list[segment_count][bitrate])
    tiles = []
    tiles_in_segment = []
    last_segment = -1
    pre_ulrs_dict = None # (tile : [bitrate, stream_priotyt]), created by ABR
    urls_dict = None # (file_url : stream_prioryt), created after pre_url_dict mapping
    emergency_flag = False
    total_segment_size = None
    #tread variables
        #t_list = []
    threads = []

    # tile reader
    if TILE_READER == "NARROW":
        tileReader = NarrowReader(dash_player.playback_timer, HEAD_TRACE_PATH+'move_alert.csv', segment_duration)
    elif TILE_READER == "ALL":
        tileReader = AllReader(dash_player.playback_timer, total_tiles, segment_duration)
    elif TILE_READER.upper() == "PERFPREDICT":
        tileReader = PerfPredict(dash_player.playback_timer, HEAD_TRACE_PATH+'move_alert.csv', segment_duration, PREDICT_TIME)

    #tile getter
    if TILE_GETTER or TILE_READER == "PERFPREDICT":
        dash_player.tile_getter = NarrowReader(dash_player.playback_timer, HEAD_TRACE_PATH+'move_alert.csv', segment_duration)
        dash_player.tile_getter.start()
    else:
        dash_player.tile_getter = tileReader

    tileReader.start()

    # waiting for the player to finish playing
    segment_number = dp_object.video[current_bitrate].start
    downloaded_flag = False
    while dash_player.playback_state not in dash_buffer.EXIT_STATES:
        if segment_number <= len(dp_list.keys()):

            segment_number, n_tiles = tileReader.get_tiles()

            for tile in n_tiles:
                if tile not in tiles:
                    tiles.append(tile)

            if last_segment != segment_number:
                tiles_in_segment = []

            if BITRATE is not None:
                pass

            elif playback_type.upper() == "BASIC" and last_segment != segment_number:
                current_bitrate, average_dwn_time = basic_dash3.basic_dash3(
                segment_number, bitrates, average_dwn_time, recent_download_sizes, 
                previous_segment_times, current_bitrate)

            elif playback_type.upper() == 'SMART' and last_segment != segment_number:
                if not weighted_mean_object:
                    weighted_mean_object = WeightedMean(config_dash.SARA_SAMPLE_COUNT)
                    config_dash.LOG.debug("Initializing the weighted Mean object")

                current_bitrate, delay = weighted_dash.weighted_dash(bitrates, dash_player, 
                        weighted_mean_object.weighted_mean_rate, 
                            current_bitrate, get_segment_sizes(dp_object, segment_number))

            # priority = 0xff
            if TP:
                lowP, highP = linePriority(tiles)

            if MS:
                threads = []
                download_sizes_t = []

            if dash_player.current_segment != None and len(dash_player.emergency_tiles) > 0:
                segment_number = get_player_segment_number(dash_player)
                tiles = dash_player.emergency_tiles
                emergency_flag = True

            total_segment_size = 0
            for tile in tiles:
                # print("{} {} {}".format(segment_number, bitrate, tile))

                if TP and tile in lowP and bitrates.index(current_bitrate) > 0:
                    priority = 0x00
                    bitrate = bitrates[bitrates.index(current_bitrate) - 1]

                else:
                    priority = 0xff
                    bitrate = current_bitrate

                path_to_tiles = dp_list[segment_number][bitrate]

                if not downloaded_tiles[segment_number][bitrate][tile]:
                    downloaded_tiles[segment_number][bitrate][tile] = True
                    downloaded_flag = True

                    segment_url = urllib.parse.urljoin(domain, path_to_tiles[tile])

                    if not MS:
                        config_dash.LOG.info("{}: Downloading file {}".format(playback_type.upper(), segment_url))
                        
                        try:
                            start_time = timeit.default_timer()
                            segment_size, segment_filename = download_segment(segment_url, file_identifier, download)
                            segment_download_time = timeit.default_timer() - start_time
                            previous_segment_times.append(segment_download_time)
                            config_dash.LOG.info("{}: Downloaded segment {}".format(playback_type.upper(), segment_url))
                        except IOError as e:
                            config_dash.LOG.error('Unable to save segment %s' % e)
                            return None

                        tiles_in_segment.append(tile)
                        segment_size = dp_object.video[bitrate].segment_size

                        recent_download_sizes.append(segment_size)
                        segment_files.append(segment_filename)

                        #update tje JSON information
                        segment_name = os.path.split(segment_url)[1]
                        if 'segment_info' not in config_dash.JSON_HANDLE:
                            config_dash.JSON_HANDLE['segment_info'] = list()
                        config_dash.JSON_HANDLE['segment_info'].append((segment_name, segment_size, segment_download_time))


                        config_dash.LOG.info('Downloaded {}. Size = {} in {} seconds'.format(
                                            segment_url, segment_size, str(segment_download_time)))

                        total_downloaded += segment_size
                        total_segment_size += segment_size

                    else: 
                        #download_thread(playback_type, segment_url, priority, tiles_in_segment, recent_download_sizes, segment_files)
                        t = Thread(target=download_thread, daemon=True,
                                    args=(playback_type, tile, segment_url, priority, file_identifier, download, 
                                            previous_segment_times, tiles_in_segment, download_sizes_t, segment_files))
                        threads.append(t)

            if len(threads) > 0:
                downloaded_flag = True
                start_time = timeit.default_timer()
                for t in threads:
                    t.start()

                for t in threads:
                    t.join()

                segment_download_time = timeit.default_timer() - start_time

                recent_download_sizes += download_sizes_t
                total_segment_size = sum(download_sizes_t)
                total_downloaded += total_segment_size
                config_dash.LOG.info('Downloaded {}. Size = {} in {} seconds'.format(
                                        segment_url, segment_size, str(segment_download_time)))

            if playback_type.upper() == 'SMART' and weighted_mean_object and last_segment != segment_number:
                print(get_segment_sizes(dp_object, segment_number))
                weighted_mean_object.update_weighted_mean(get_segment_sizes(dp_object, segment_number)[current_bitrate], segment_download_time)


            if downloaded_flag:
                config_dash.LOG.info("{} : The total downloaded = {}, segment_size = {}, segment_number = {}".format(
                                    playback_type.upper(), total_downloaded, segment_size, segment_number))
                downloaded_flag = False

            if NO_KEEP_ALIVE:
                glueConnection.closeConnection()

            if emergency_flag:
                dash_player.current_segment['tiles_in_segment'].extend(tiles)
                emergency_flag = False

            if last_segment != segment_number:
                segment_info = {'playback_length' : video_segment_duration,
                                'bitrate' : current_bitrate,
                                'segment_number' : segment_number,
                                'tiles_in_segment' : tiles_in_segment}

                last_segment = segment_number
                dash_player.write(segment_info)

        #old:
        #segment_number = dash_player.playback_timer.time()//dp_object.video[current_bitrate].segment_duration + 1

        if previous_bitrate:
            if previous_bitrate < current_bitrate:
                config_dash.JSON_HANDLE['playback_info']['up_shifts'] += 1
            elif previous_bitrate > current_bitrate:
                config_dash.JSON_HANDLE['playback_info']['down_shifts'] += 1
            previous_bitrate = current_bitrate


    glueConnection.stopLogging()
    glueConnection.closeConnection()

    if not download:
        clean_files(file_identifier)

def get_segment_sizes(dp_object, segment_number):
    """ Module to get the segment sizes for the segment_number
    :param dp_object:
    :param segment_number:
    :return:
    """
    segment_sizes = {bitrate: dp_object.video[bitrate].segment_size for bitrate in dp_object.video}
    config_dash.LOG.debug("The segment sizes of {} are {}".format(segment_number, segment_sizes))
    return segment_sizes


def get_average_segment_sizes(dp_object):
    """
    Module to get the avearge segment sizes for each bitrate
    :param dp_object:
    :return: A dictionary of aveage segment sizes for each bitrate
    """
    average_segment_sizes = dict()
    for bitrate in dp_object.video:
        segment_sizes = dp_object.video[bitrate].segment_sizes
        segment_sizes = [float(i) for i in segment_sizes]
        try:
            average_segment_sizes[bitrate] = sum(segment_sizes)/len(segment_sizes)
        except ZeroDivisionError:
            average_segment_sizes[bitrate] = 0
    config_dash.LOG.info("The avearge segment size for is {}".format(list(average_segment_sizes.items())))
    return average_segment_sizes


def clean_files(folder_path):
    """
    :param folder_path: Local Folder to be deleted
    """
    if os.path.exists(folder_path):
        try:
            for video_file in os.listdir(folder_path):
                file_path = os.path.join(folder_path, video_file)
                if os.path.isfile(file_path):
                    os.unlink(file_path)
            os.rmdir(folder_path)
        except OSError as e:
            config_dash.LOG.info("Unable to delete the folder {}. {}".format(folder_path, e))
        config_dash.LOG.info("Deleted the folder '{}' and its contents".format(folder_path))


def start_playback_all(dp_object, domain):
    """ Module that downloads the MPD-FIle and download all the representations of 
        the Module to download the MPEG-DASH media.
    """
    # audio_done_queue = Queue()
    video_done_queue = Queue()
    processes = []
    file_identifier = id_generator(6)
    config_dash.LOG.info("File Segments are in %s" % file_identifier)
    # for bitrate in dp_object.audio:
    #     # Get the list of URL's (relative location) for the audio
    #     dp_object.audio[bitrate] = read_mpd.get_url_list(bitrate, dp_object.audio[bitrate],
    #                                                      dp_object.playback_duration)
    #     # Create a new process to download the audio stream.
    #     # The domain + URL from the above list gives the
    #     # complete path
    #     # The fil-identifier is a random string used to
    #     # create  a temporary folder for current session
    #     # Audio-done queue is used to exchange information
    #     # between the process and the calling function.
    #     # 'STOP' is added to the queue to indicate the end
    #     # of the download of the sesson
    #     process = Process(target=get_media_all, args=(domain, (bitrate, dp_object.audio),
    #                                                   file_identifier, audio_done_queue))
    #     process.start()
    #     processes.append(process)

    for bitrate in dp_object.video:
        dp_object.video[bitrate] = read_mpd.get_url_list(bitrate, dp_object.video[bitrate],
                                                         dp_object.playback_duration,
                                                         dp_object.video[bitrate].segment_duration)
        # Same as download audio
        process = Process(target=get_media_all, args=(domain, (bitrate, dp_object.video),
                                                      file_identifier, video_done_queue))
        process.start()
        processes.append(process)
    for process in processes:
        process.join()
    count = 0
    for queue_values in iter(video_done_queue.get, None):
        bitrate, status, elapsed = queue_values
        if status == 'STOP':
            config_dash.LOG.critical("Completed download of %s in %f " % (bitrate, elapsed))
            count += 1
            if count == len(dp_object.video):
                # If the download of all the videos is done the stop the
                config_dash.LOG.critical("Finished download of all video segments")
                break


def print_interruptions_info():
    start_time = config_dash.JSON_HANDLE['playback_info']['start_time']
    interruptions = config_dash.JSON_HANDLE['playback_info']['interruptions']
    events = list(filter(lambda x: x['timeframe'][0] > start_time + 15, interruptions['events']))
    durations = [
        x['timeframe'][1] - x['timeframe'][0] for x in events
    ]

    if len(durations) == 0:
        print("no interruptions encountered")
        return
    elif len(durations) == 1:
        print("only a single interruption encountered")
        print("length: ", durations[0])
        return

    mean = sum(durations) / len(durations)
    stddev = math.sqrt(sum([(x - mean)**2 for x in durations]) / (len(durations) - 1))

    print(f"interrupts: {len(durations)}")
    print(f"total duration: {sum(durations)}")
    print(f"mean: {mean}")
    print(f"stddev: {stddev}")


def create_arguments(parser):
    """ Adding arguments to the parser """
    parser.add_argument('-m', '--MPD',                   
                        help="Url to the MPD File")
    parser.add_argument('-l', '--LIST', action='store_true',
                        help="List all the representations")
    parser.add_argument('-p', '--PLAYBACK',
                        default=DEFAULT_PLAYBACK,
                        help="Playback type (basic, sara, netflix, or all)")
    parser.add_argument('-n', '--SEGMENT_LIMIT',
                        default=SEGMENT_LIMIT,
                        help="The Segment number limit")
    parser.add_argument('-d', '--DOWNLOAD', action='store_true',
                        default=False,
                        help="Keep the video files after playback")
    parser.add_argument('-q', '--QUIC', action='store_true',
                        default=False,
                        help="Use QUIC as protocol")
    parser.add_argument('-mp', '--MP', action='store_true',
                        default=False,
                        help="Activate multipath in QUIC")
    parser.add_argument('-nka', '--NO_KEEP_ALIVE', action='store_true',
                        default=False,
                        help="Keep alive connection to Server")
    parser.add_argument('-s', '--SCHEDULER',
                        default='lowRTT',
                        help="Scheduler in multipath usage (lowRTT, RR, redundant)")
    parser.add_argument('-c', '--CC',
                        default='olia',
                        help="Congestion control scheme")
    parser.add_argument('-f', '--fec', action='store_true', default=False,
                        help='Enable FEC')
    parser.add_argument('-b', '--BITRATE', default=None,
                        help='Force to use a specific bitrate')
    parser.add_argument('--fecConfig', default='xor4',
                        help='FEC configuration to use')
    parser.add_argument('-t', '--TIME-LIMIT', type=int, default=None,
                        help="stop playback after this many seconds")
    parser.add_argument('-tr', '--TILE_READER', 
                        default="NARROW",
                        help="TileDelivery object for client")
    parser.add_argument('-tg', '--TILE_GETTER', action='store_true', 
                        default=False,
                        help="TileDelivery object for buffer")
    parser.add_argument('-pt', '--PREDICT-TIME', 
                        default=0.5,
                        help="Prediction time")
    parser.add_argument('-ms', '--MS', action='store_true', 
                        default=False,
                        help="Use mult-stream")
    parser.add_argument('-tp', '--TP', 
                        default="UNI",
                        help="Priority for tiles in the center")
    parser.add_argument('-oz', '--OUTER_ZONE', 
                        default=False,
                        help="zone outside FoV type")
    parser.add_argument('-ozs', '--OUTER_ZONE_SIZE', 
                        default=0,
                        help="zone outside FoV size")
    parser.add_argument('-br', '--BITRATE_REDUCTION', action='store_true',
                        default=False,
                        help="reduce bitrate with priority")
    parser.add_argument('-sm', '--STREAM_MAX', 
                        default=100,
                        help="max concurrent streams")
    parser.add_argument('-bm', '--MAX_BUFFER_SIZE', 
                        default=0,
                        help="max segmets in buffer")

def main():
    """ Main Program wrapper """
    # configure the log file
    # Create arguments
    parser = ArgumentParser(description='Process Client parameters')
    create_arguments(parser)
    args = parser.parse_args()
    globals().update(vars(args))
    configure_log_file(playback_type=PLAYBACK.lower())
    config_dash.JSON_HANDLE['playback_type'] = PLAYBACK.lower()
    if QUIC:
        config_dash.JSON_HANDLE['transport'] = 'quic'
    else: 
        config_dash.JSON_HANDLE['transport'] = 'tcp'
    if MP:
        config_dash.JSON_HANDLE['scheduler'] = SCHEDULER
    else:
        config_dash.JSON_HANDLE['scheduler'] = 'singlePath'
    if fec:
        config_dash.JSON_HANDLE['fecConfig'] = fecConfig
    else:
        config_dash.JSON_HANDLE['fecConfig'] = 'none'
    config_dash.JSON_HANDLE['congestionControl'] = CC
    if not MPD:
        print("ERROR: Please provide the URL to the MPD file. Try Again..")
        return 1

    #glueConnection.setupFEC(fec, fecConfig)
    glueConnection.setupLib(MS)
    glueConnection.setupPM(QUIC, MP, MS, not NO_KEEP_ALIVE, SCHEDULER, CC)

    config_dash.LOG.info('Downloading MPD file %s' % MPD)
    # Retrieve the MPD files for the video
    mpd_file = get_mpd(MPD)
    domain = get_domain_name(MPD)
    dp_object = DashPlayback()
    
    # Reading the MPD file created
    dp_object, video_segment_duration = read_mpd.read_mpd(mpd_file, dp_object, BITRATE)
    
    config_dash.LOG.info("The DASH media has %d video representations" % len(dp_object.video))
    if LIST:
        # Print the representations and EXIT
        print_representations(dp_object)
        return None
    if "all" in PLAYBACK.lower():
        if mpd_file:
            config_dash.LOG.critical("Start ALL Parallel PLayback")
            start_playback_all(dp_object, domain)
    elif "basic" in PLAYBACK.lower():
        config_dash.LOG.critical("Started Basic-DASH Playback")
        start_playback_smart(dp_object, domain, "BASIC", DOWNLOAD, video_segment_duration)
    elif "sara" in PLAYBACK.lower():
        config_dash.LOG.critical("Started SARA-DASH Playback")
        start_playback_smart(dp_object, domain, "SMART", DOWNLOAD, video_segment_duration)
    elif "netflix" in PLAYBACK.lower():
        config_dash.LOG.critical("Started Netflix-DASH Playback")
        start_playback_smart(dp_object, domain, "NETFLIX", DOWNLOAD, video_segment_duration)
    elif "maguro" in PLAYBACK.lower():
        config_dash.LOG.critical("Started maguro-DASH Playback")
        start_playback_smart(dp_object, domain, "MAGURO", DOWNLOAD, video_segment_duration)
    elif "unagi" in PLAYBACK.lower():
        config_dash.LOG.critical("Started unagi-DASH Playback")
        start_playback_smart(dp_object, domain, "UNAGI", DOWNLOAD, video_segment_duration)
    else:
        config_dash.LOG.error("Unknown Playback parameter {}".format(PLAYBACK))
        return 1

    write_json()
    print_interruptions_info()
    print("total stream connection loss: {}".format(config_dash.JSON_HANDLE['playback_info']['connection_loss']))
    os.system('touch /home/vagrant/workspace/Dash360-sa-ecf/dash/temp')
    return 0

if __name__ == "__main__":
    sys.exit(main())
