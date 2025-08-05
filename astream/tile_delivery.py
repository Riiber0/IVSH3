from abc import abstractmethod
import pandas as pd
from collections import deque
from stop_watch import StopWatch
import threading
import time

class TileDelivery:
    """class template"""
    def __init__(self, timer, segment_duration):
        """timer : dash_player playback_timer"""
        self.playback_timer = timer
        self.segment_duration = segment_duration
        self.segment = 1
        self.last_segment = 1
        self.lock = threading.Lock()
    
    @abstractmethod
    def get_tiles(self):
        """ Return tile segment and needed tiles"""

    @abstractmethod
    def start(self):
        """ thread setup and start """

class NarrowReader(TileDelivery):
    """reads tiles from csv"""
    def __init__(self, timer, tiledataset, segment_duration):
        super().__init__(timer, segment_duration)
        self.df = pd.read_table(tiledataset, header=None, sep=',')
        self.df = self.df.iloc[1:]
        #self.df = self.df[0].str.split(',', expand=True)
        self.tiles = None
        self.reader = None

    def initialize_reader(self):
        df_index = 0

        self.lock.acquire()
        move_alert_l = deque(self.df[0])
        move_alert_time = float(move_alert_l.popleft())
        self.tiles = self.df.iloc[df_index][1:]
        self.tiles = list(self.tiles.dropna())
        self.tiles = [int(tile) for tile in self.tiles]
        self.lock.release()

        while True:
            #change segment
            self.segment = self.playback_timer.time()//self.segment_duration + 1
            if self.playback_timer.time() >= move_alert_time:
                self.lock.acquire()

                #change tiles
                df_index += 1
                if df_index == len(self.df):
                    self.lock.release()
                    return
                self.tiles = self.df.iloc[df_index][1:]
                self.tiles = list(self.tiles.dropna())
                self.tiles = [int(tile) for tile in self.tiles]
                self.lock.release()

                #change next alert time
                move_alert_time = float(move_alert_l.popleft())
            
            time.sleep(0.01)


    def start(self):
        self.reader = threading.Thread(target=self.initialize_reader)
        self.reader.daemon = True
        self.reader.start()

    def get_tiles(self):
        self.lock.acquire()
        segment = self.segment
        tiles = self.tiles
        self.lock.release()

        return segment, tiles

class PerfPredict(TileDelivery):
    """reads tiles from csv"""
    def __init__(self, timer, tiledataset, segment_duration, predict_time=0.5):
        super().__init__(timer, segment_duration)
        self.df = pd.read_table(tiledataset, header=None, sep=',')
        self.df = self.df.iloc[1:]
        #self.df = self.df[0].str.split(',', expand=True)
        self.tiles = None
        self.reader = None
        self.predict_time = predict_time

    def initialize_reader(self):
        df_index = 0

        self.lock.acquire()
        move_alert_l = deque(self.df[0])
        move_alert_time = float(move_alert_l.popleft())
        tiles_sum = list()
        tiles_sum = self.df.iloc[df_index][1:]
        tiles_sum = tiles_sum.dropna()
        tiles_sum = list(tiles_sum)
        tiles_sum = [int(tile) for tile in tiles_sum]

        tiles_d = dict()
        for tile in tiles_sum:
            tiles_d[tile] = move_alert_time

        i = 0.0
        while i <= self.predict_time:
            if i >= move_alert_time:
                #acumulate tiles for playback start
                df_index += 1
                new_tiles = self.df.iloc[df_index][1:]
                new_tiles = list(new_tiles.dropna())
                new_tiles = [int(tile) for tile in new_tiles]

                new_tiles_d = dict()
                for tile in new_tiles:
                    new_tiles_d[tile] = move_alert_time
                
                tiles_d = {**new_tiles_d, **tiles_d}

                #change next alert time
                move_alert_time = float(move_alert_l.popleft())

            i += 0.01
        self.lock.release()

        self.tiles = tiles_d
        while True:
            #change segment
            self.segment = (self.playback_timer.time() + self.predict_time)//self.segment_duration + 1

            if self.segment != self.last_segment:
                self.tiles = {}

            if (self.playback_timer.time() + self.predict_time) >= move_alert_time:

                #change tiles
                self.lock.acquire()
                df_index += 1
                if df_index == len(self.df):
                    self.lock.release()
                    return


                current_tiles = [int(tile) for tile in self.df.iloc[df_index][1:].dropna()]
                new_tiles = [tile for tile in current_tiles if tile not in self.tiles]

                new_tiles_d = dict()
                for tile in new_tiles:
                    new_tiles_d[tile] = move_alert_time

                self.tiles = {**new_tiles_d, **self.tiles}
                self.lock.release()

                #change next alert time
                move_alert_time = float(move_alert_l.popleft())
            
            self.last_segment = self.segment


    def start(self):
        self.reader = threading.Thread(target=self.initialize_reader)
        self.reader.daemon = True
        self.reader.start()

    def get_tiles(self):
        self.lock.acquire()
        segment = self.segment
        tiles = self.tiles
        self.lock.release()

        return segment, tiles

class AllReader(TileDelivery):
    """return list with every tile"""
    def __init__(self, timer, total_tiles, segment_duration):
        super().__init__(timer, segment_duration)
        self.total_tiles = total_tiles
        self.tile_list = None
        
    def start(self):
        self.tile_list = [i for i in range(1, self.total_tiles+1)]

    def get_tiles(self):
        segment = self.playback_timer.time()//self.segment_duration + 1
        return segment, self.tile_list

if __name__ == '__main__':
    """test"""
    r = StopWatch()
    r.start()
    d = PerfPredict(r, "move_alert.csv", 4, 3.5)
    d.start()
    print(d.get_tiles())
        
    
    while d.reader.is_alive():
        time.sleep(0.5)
        print(d.get_tiles())
    

    print('fim')
    
