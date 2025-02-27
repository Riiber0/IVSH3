import io
import read_mpd
from configure_log_file import configure_log_file
from collections import defaultdict

"""
class MediaObject(object):
    def __init__(self):
        self.min_buffer_time = None
        self.start = None
        self.timescale = None
        self.segment_duration = None
        self.initialization = None
        self.base_url = None
        self.url_list = list()
"""

configure_log_file(playback_type='basic')
mpd_file = open('dash_tiled.mpd', 'rb')
dp_object = read_mpd.DashPlayback()
dp_object, video_segment_duration = read_mpd.read_mpd(mpd_file, dp_object, None)

dp_list = dict()

for bitrate in dp_object.video:
    # Getting the URL list for each bitrate
    dp_object.video[bitrate] = read_mpd.get_url_list(dp_object.video[bitrate], video_segment_duration,
                                                     dp_object.playback_duration, bitrate)

    for tile_id in dp_object.video[bitrate].url_list:
        media_urls = dp_object.video[bitrate].url_list[tile_id]

        for segment_count, segment_url in enumerate(media_urls, dp_object.video[bitrate].start):
            if segment_count not in dp_list.keys():
                dp_list[segment_count] = dict()

            if bitrate not in dp_list[segment_count].keys():
                dp_list[segment_count][bitrate] = dict()

            if tile_id not in dp_list[segment_count][bitrate].keys():
                dp_list[segment_count][bitrate][tile_id] = dict()

            dp_list[segment_count][bitrate][tile_id] = segment_url

ssims = dict()
sizes = dict()
for bitrate in dp_list[segment_count]:
    ssims[bitrate] = dp_object.video[bitrate].ssim
    sizes[bitrate] = dp_object.video[bitrate].segment_size/1000000

print(ssims)
print(sizes)
