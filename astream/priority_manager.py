from abc import abstractmethod
import threading
import config_dash

class PriorityManager:
    def __init__(self):
        self.available_priorities = 255
        self.lock = threading.Lock()
        self.priorities = dict()
        for i in range(255, -1, -1):
            self.priorities[i] = 0

    @abstractmethod
    def get_priority(self, tiles, segment_increase):
        """ returns dict """

    @abstractmethod
    def update_priorities(self, priority):
        pass

    @abstractmethod
    def lock_priority(self, priority):
        pass

class UniPriority(PriorityManager):
    def __init__(self, max_streams):
        self.sem = threading.BoundedSemaphore(max_streams)

    def get_priority(self, tiles, segment_increase):
        ret = dict()
        for tile in tiles.keys():
            ret[tile] = 0xff

        return ret

    def update_priorities(self, priority):
        self.sem.release()

    def lock_priority(self, priority):
        self.sem.acquire()

class GroupPriority(PriorityManager):
    def __init__(self, priority_spaces, max_streams):
        super().__init__()
        self.space_size = 255//priority_spaces
        self.extra_space = 255%priority_spaces
        self.last_priority = [0] * priority_spaces
        self.max_streams = max_streams
        self.sem = list()
        for i in range(0, priority_spaces):
            max_space_streams = max_streams//priority_spaces
            self.sem.append(threading.BoundedSemaphore(max_space_streams))

    def get_priority(self, tiles, segment_increase):
        ret = dict()
        times = list(set(tiles.values()))
        times.sort()

        if self.last_priority[segment_increase] != 0:
            priority = self.last_priority[segment_increase] - 1
        else:
            priority = 255 - segment_increase * self.space_size

        priority_map = dict()
        for time in times:
            priority_map[time] = priority
            if priority - 1 > 0:
                priority = priority - 1
            #if priority <= 255 - (segment_increase+1) * self.space_size:
            #    break

        for tile in tiles.keys():
            p = priority_map[tiles[tile]]
            ret[tile] = p
            self.lock.acquire()
            self.priorities[p] += 1
            self.lock.release()

        self.last_priority[segment_increase] = priority+1
        return ret

    def update_priorities(self, priority):
        if priority > 255 or priority < 0:
            print(priority)
        self.lock.acquire()
        if self.priorities[priority] > 0:
            self.priorities[priority] -= 1

        segment_increase = (255 - priority)//self.space_size
        self.sem[segment_increase].release()
        #print('segment increase : {}'.format(segment_increase))
        if priority == self.last_priority[segment_increase]:
            for i in range(priority, 255-(segment_increase*self.space_size) + 1):
                if self.priorities[i] == 0:
                    self.last_priority[segment_increase] = i+1
                else:
                    break

            if self.last_priority[segment_increase] > 255-(segment_increase*self.space_size):
                self.last_priority[segment_increase] = 0

        self.lock.release()

    def lock_priority(self, priority):
        segment_increase = (255 - priority)//self.space_size
        self.sem[segment_increase].acquire()


if __name__ == "__main__":
    tiles = {47: 1.5, 48:0.99, 52:1.5, 53:0.66}
    print(tiles)
    print('Group Priority')
    p = GroupPriority(1, 9)
    
    tiles_p = p.get_priority(tiles, 0)
    print(tiles_p)
    p.lock_priority(tiles_p[47])
    p.lock_priority(tiles_p[48])
    p.lock_priority(tiles_p[53])
    p.update_priorities(tiles_p[47])
    p.update_priorities(tiles_p[48])
    p.update_priorities(tiles_p[53])
    print(p.get_priority(tiles, 0))

    print('Uni Priority')
    p = UniPriority(9)
    
    tiles_p = p.get_priority(tiles, 2)
    print(tiles_p)
    p.lock_priority(tiles_p[47])
    p.lock_priority(tiles_p[48])
    p.lock_priority(tiles_p[53])
    p.update_priorities(tiles_p[47])
    p.update_priorities(tiles_p[48])
    p.update_priorities(tiles_p[53])
    print(p.get_priority(tiles, 2))


