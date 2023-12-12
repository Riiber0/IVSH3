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
import json
import math
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
        raise ValueError("invalid segment_size, connection dropped")
    return segment_size, segment_name


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
    dash_player = dash_buffer.DashPlayer(dp_object.playback_duration, video_segment_duration)
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
    segment_duration = 0
    segment_size = segment_download_time = None
    # Netflix Variables
    average_segment_sizes = netflix_rate_map = None
    netflix_state = "INITIAL"

    # movedataset
    df = pd.read_table('move_alert.csv', header=None)
    df = df.iloc[1:]
    df = df[0].str.split(',', expand=True)
    df_index = 1
    move_alert_l = deque(df[0])
    move_alert_time = float(move_alert_l.popleft())
    tiles = df.iloc[df_index][1:]
    tiles = [tile for tile in tiles if tile != '']

    # waiting for the player to finish playing
    segment_number = dp_object.video[current_bitrate].start
    print("start while")
    while dash_player.playback_state not in dash_buffer.EXIT_STATES:
        if segment_number <= len(dp_list.keys()):
            if dash_player.playback_timer.time() >= move_alert_time:
                #change tiles
                df_index += 1
                tiles = df.iloc[df_index][1:]
                tiles = [tile for tile in tiles if tile != '']
                #change segment
                move_alert_time = float(move_alert_l.popleft())

            path_to_tiles = dp_list[segment_number][current_bitrate]
            for tile in tiles:
                if not downloaded_tiles[segment_number][current_bitrate][int(tile)]:
                    downloaded_tiles[segment_number][current_bitrate][int(tile)] = True

                    segment_url = urllib.parse.urljoin(domain, path_to_tiles[int(tile)])
                    
                    try:
                        download_segment(segment_url, file_identifier, download)
                    except IOError as e:
                        config_dash.LOG.error('Unable to save segment %s' % e)
                        return None

        segment_number = dash_player.playback_timer.time()//dp_object.video[current_bitrate].segment_duration + 1
        print(segment_number)
        print(dash_player.playback_timer.time())
        print(dash_player.playback_state)

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
    segment_sizes = {bitrate: dp_object.video[bitrate].segment_sizes[segment_number] for bitrate in dp_object.video}
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
        return None

    #glueConnection.setupFEC(fec, fecConfig)
    glueConnection.setupPM(QUIC, MP, not NO_KEEP_ALIVE, SCHEDULER, CC)

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
    else:
        config_dash.LOG.error("Unknown Playback parameter {}".format(PLAYBACK))
        return None

    write_json()
    print_interruptions_info()

if __name__ == "__main__":
    sys.exit(main())
