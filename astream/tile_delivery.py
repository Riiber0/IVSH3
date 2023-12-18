from abc import abstractmethod
import pandas as pd
from collections import deque
from stop_watch import StopWatch
import threading
import time

class TileDelivery:
    """class template"""
    def __init__(self, timer):
        """timer : dash_player playback_timer"""
        self.playback_timer = timer
    
    @abstractmethod
    def get_tiles(self):
        """ Return needed tiles"""

class DataReader(TileDelivery):
    """reads tiles from csv"""
    def __init__(self, timer, tiledataset):
        super().__init__(timer)
        self.df = pd.read_table(tiledataset, header=None)
        self.df = self.df.iloc[1:]
        self.df = self.df[0].str.split(',', expand=True)
        self.tiles = None
        self.reader = None

    def initialize_reader(self):
        df_index = 0
        move_alert_l = deque(self.df[0])
        move_alert_time = float(move_alert_l.popleft())
        self.tiles = self.df.iloc[df_index][1:]
        self.tiles = [int(tile) for tile in self.tiles if tile != '']

        while True:
            if self.playback_timer.time() >= move_alert_time:
                #change tiles
                df_index += 1
                if df_index == len(self.df):
                    return
                self.tiles = self.df.iloc[df_index][1:]
                self.tiles = [int(tile) for tile in self.tiles if tile != '']
                #change segment
                move_alert_time = float(move_alert_l.popleft())
            
            time.sleep(0.01)


    def start(self):
        self.reader = threading.Thread(target=self.initialize_reader)
        self.reader.daemon = True
        self.reader.start()

    def get_tiles(self):
        while(self.tiles == None):
            time.sleep(0.05)

        return self.tiles

if __name__ == '__main__':
    """test"""
    r = StopWatch()
    r.start()
    d = DataReader(r, 'move_alert.csv')
    d.start()
        
    while d.reader.is_alive():
        time.sleep(0.5)
        print(d.get_tiles())

    print('fim')
    
