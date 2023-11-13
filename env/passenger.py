import math
import numpy as np
from consts import PASSENGER_SPEED


def get_distance(lat1, lon1, lat2, lon2):
    # in meter
    EARTH_RADIUS = 6378.137
    radlat1, radlon1 = lat1 * math.pi / 180.0, lon1 * math.pi / 180.0
    radlat2, radlon2 = lat2 * math.pi / 180.0, lon2 * math.pi / 180.0
    a, b = radlat1 - radlat2, radlon1 - radlon2
    s = 2 * math.asin(
        math.sqrt(math.pow(math.sin(a / 2), 2) + math.cos(radlat1) * math.cos(radlat2) * math.pow(math.sin(b / 2), 2)))
    s = s * EARTH_RADIUS
    s *= 1000
    return s


class Passenger:

    def __init__(self, pas_id: int, start_pos: tuple, start_loc: int, arrive_time: int, end_pos: tuple, end_loc: int):
        self.pas_id = pas_id  # 用户编号
        self.start_pos = start_pos  # 出发坐标
        self.start_loc = start_loc  # 出发站点
        self.arr_t = arrive_time  # 到站时刻
        self.end_pos = end_pos  # 到站坐标
        self.end_loc = end_loc  # 到站站点

        self.down_loc = None  # 下车站点, 用于mode='multi'

        # snapshot
        self.on_t = None  # 上车时刻
        self.down_t = None  # 下车时刻

        # record
        self.start_t = None  # 出发时刻
        self.end_t = None  # 结束时刻
        self.on_bus = None

        self.move_t = 0  # 到达站点前或离开站点后移动的时间
        self.move_dist = 0  # 到达站点前或离开站点后移动的距离
        self.travel_t = 0  # 车上经过的时间
        self.bus_wait_t = 0  # 在车上的等待时间（停站）
        self.station_wait_t = 0  # 在站点等待的时间
        self.full_jour_t = 0  # 出行全程时间

    def __repr__(self):
        return f'Passenger_{self.pas_id}'

    def get_start_t(self, line):
        """
        已知起点到站时间，获取出发时间

        :return:
        """
        sta_lat, sta_lon = self.start_pos
        if isinstance(self.start_loc, (int, np.integer)):
            arr_lat, arr_lon = line.loc_list[self.start_loc - 1]
        else:
            main_id, side_id, side_order = map(int, self.start_loc.split('#'))
            arr_lat = line.side_line[str(main_id) + '#' + str(side_id)].side_stations[side_order]['lat']
            arr_lon = line.side_line[str(main_id) + '#' + str(side_id)].side_stations[side_order]['lon']
        arr_dist = get_distance(lat1=sta_lat, lon1=sta_lon, lat2=arr_lat, lon2=arr_lon)

        # test_lat, test_lon = line.loc_list[main_id - 1]
        # print(get_distance(lat1=sta_lat, lon1=sta_lon, lat2=test_lat, lon2=test_lon), arr_dist)

        arr_duration = int(arr_dist / PASSENGER_SPEED)
        self.start_t = self.arr_t - arr_duration

    def get_end_t(self, line, mode):
        """
        已知终点到站时间，获取行程结束时间

        :return:
        """
        sel_loc = self.end_loc if mode in ['baseline', 'single'] else self.down_loc
        end_lat, end_lon = self.end_pos
        if isinstance(sel_loc, (int, np.integer)):
            down_lat, down_lon = line.loc_list[sel_loc-1]
        else:
            main_id, side_id, side_order = map(int, sel_loc.split('#'))
            down_lat = line.side_line[str(main_id) + '#' + str(side_id)].side_stations[side_order]['lat']
            down_lon = line.side_line[str(main_id) + '#' + str(side_id)].side_stations[side_order]['lon']
        end_dist = get_distance(lat1=end_lat, lon1=end_lon, lat2=down_lat, lon2=down_lon)

        # test_lat, test_lon = line.loc_list[main_id - 1]
        # print(get_distance(lat1=end_lat, lon1=end_lon, lat2=test_lat, lon2=test_lon), end_dist)

        end_duration = int(end_dist / PASSENGER_SPEED)
        self.end_t = self.down_t + end_duration

    def get_statistics(self, line, mode: str = 'single'):
        """乘客出行统计数据"""
        self.get_start_t(line=line)
        self.get_end_t(line=line, mode=mode)

        self.move_t = self.arr_t - self.start_t + self.end_t - self.down_t
        self.move_dist = self.move_t * PASSENGER_SPEED
        self.travel_t = self.down_t - self.on_t
        self.station_wait_t = self.on_t - self.arr_t
        self.full_jour_t = self.end_t - self.start_t

    def add_bus_wait(self, seconds: int):
        """中途停站时用以修改"""
        self.bus_wait_t += seconds
