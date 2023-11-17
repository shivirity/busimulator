import heapq
import logging
import random
import numpy as np
import pandas as pd

from consts import DIS_FIX
from env.passenger import get_distance

random.seed(42)
np.random.seed(42)


class Line:

    def __init__(self, direc: int, station_list: list, loc_list: list,
                 dist_list: list, speed_list: list, mode: str, side_line_info=None):
        self.direc = direc
        self.max_station_num = len(station_list)
        self.station_list = list(station_list)
        self.loc_list = list(loc_list)
        self.dist_list = list(dist_list)
        self.speed_list = list(speed_list)
        self.mode = mode

        # main_line (dict)
        self.main_line = None
        # side_line (dict)
        self.side_line = None

        # 生成主线
        self.create_main_line()
        if self.mode == 'multi':
            # 生成支线
            self.create_side_line(side_line_info=side_line_info)

        # consts
        self.max_wait_t = 10 * 60  # 乘客站点最大等待时间（用于随机生成出发时间）

        # passenger pool
        self.passenger_pool = self.get_passenger_info()

    def create_main_line(self):
        """
        生成主线，主线上由 main_line 字典维护

        :return:
        """
        # 站点等待人
        self.main_line = {
            i: [] for i in range(1, self.max_station_num + 1)
        }

    def create_side_line(self, side_line_info: pd.DataFrame):
        self.side_line = {
            str(side_line_info.loc[i, 'main_id']) + '#' + str(side_line_info.loc[i, 'side_id']):
                SideLine(start_lat=side_line_info.loc[i, 'start_lat'], start_lon=side_line_info.loc[i, 'start_lon'],
                         end_lat=side_line_info.loc[i, 'end_lat'], end_lon=side_line_info.loc[i, 'end_lon'],
                         main_id=side_line_info.loc[i, 'main_id'], main_speed_list=self.speed_list
                         )
            for i in range(side_line_info.shape[0])
        }

    def get_passenger_info(self):
        """
        加载所有乘客信息, 包括起始站点和起始时间, 到达站点后 reveal
        返回包含乘客出发点、时间、原出发站点、原结束站点、结束点的 dataframe

        :return: pd.Dataframe
        """
        pass_info = pd.read_csv(r'D:\mofangbus\busimulator\data\line_810\chain_data.csv', encoding='utf-8')
        pass_info = pass_info[pass_info['direction'] == self.direc].reset_index(drop=True)
        s_pos_l, s_t_l, s_loc_l, e_loc_l, e_pos_l = [], [], [], [], []
        for i in range(pass_info.shape[0]):
            up_lat, up_lon, p, up_station, down_station = pass_info.loc[i, 'up_lat'], pass_info.loc[i, 'up_lon'], \
                                                          pass_info.loc[i, 'up_time'] - 20191015000000, pass_info.loc[
                                                              i, 'current_location'], \
                                                          pass_info.loc[i, 'down_location']
            down_lat, down_lon = pass_info.loc[i, 'down_lat'], pass_info.loc[i, 'down_lon']
            up_t = int(p / 10000) * 3600 + int((p % 10000) / 100) * 60 + p % 100
            up_t -= self.get_random_t()
            ori_lat, ori_lon = self.get_random_pos(cen_lat=up_lat, cen_lon=up_lon)  # 随机生成初始出发坐标
            fin_lat, fin_lon = self.get_random_pos(cen_lat=down_lat, cen_lon=down_lon)  # 随机生成终点结束坐标
            # baseline and 单线优化
            if self.mode in ['baseline', 'single']:
                up_loc, down_loc = self.station_list.index(up_station)+1, self.station_list.index(down_station)+1
            else:  # 主线+支线
                # start location
                if (up_lat, up_lon) in self.loc_list:
                    up_station = self.loc_list.index((up_lat, up_lon)) + 1
                    if up_station == 1:
                        up_loc = up_station
                    else:
                        dist_to_side = []
                        for side in [1, 2]:
                            for side_id in range(1,
                                                 len(self.side_line[str(up_station) + '#' + str(side)].side_stations) + 1):
                                side_lat, side_lon = \
                                    self.side_line[str(up_station) + '#' + str(side)].side_stations[side_id]['lat'], \
                                    self.side_line[str(up_station) + '#' + str(side)].side_stations[side_id]['lon']
                                dist_to_side.append(get_distance(lat1=ori_lat, lon1=ori_lon, lat2=side_lat, lon2=side_lon))
                        dist_to_side.append(get_distance(lat1=ori_lat, lon1=ori_lon, lat2=up_lat, lon2=up_lon))
                        min_ind = np.argmin(dist_to_side)
                        side_1_len, side_2_len = len(self.side_line[str(up_station) + '#1'].side_stations), \
                                                 len(self.side_line[str(up_station) + '#2'].side_stations)
                        if min_ind < side_1_len:
                            up_loc = str(up_station) + '#1#' + str(min_ind + 1)
                        elif min_ind < side_1_len + side_2_len:
                            up_loc = str(up_station) + '#2#' + str(min_ind + 1 - side_1_len)
                        else:
                            up_loc = up_station
                else:
                    logging.info('main stations has changed.')
                    main_station_dist = []
                    for main_station_pos in self.loc_list:
                        main_station_dist.append(
                            get_distance(lat1=ori_lat, lon1=ori_lon, lat2=main_station_pos[0], lon2=main_station_pos[1])
                        )
                    min_two = heapq.nsmallest(2, main_station_dist)
                    min_ind = [main_station_dist.index(i) + 1 for i in min_two]
                    dist_to_side = []
                    for main_station in min_ind:
                        for side in [1, 2]:
                            for side_id in range(1,
                                                 len(self.side_line[
                                                         str(main_station) + '#' + str(side)].side_stations) + 1):
                                side_lat, side_lon = \
                                    self.side_line[str(main_station) + '#' + str(side)].side_stations[side_id]['lat'], \
                                    self.side_line[str(main_station) + '#' + str(side)].side_stations[side_id]['lon']
                                dist_to_side.append(
                                    get_distance(lat1=ori_lat, lon1=ori_lon, lat2=side_lat, lon2=side_lon))
                    main_lat_1, main_lon_1 = self.loc_list[min_ind[0] - 1]
                    main_lat_2, main_lon_2 = self.loc_list[min_ind[1] - 1]
                    dist_to_side.append(get_distance(lat1=ori_lat, lon1=ori_lon, lat2=main_lat_1, lon2=main_lon_1))
                    dist_to_side.append(get_distance(lat1=ori_lat, lon1=ori_lon, lat2=main_lat_2, lon2=main_lon_2))
                    min_side_ind = np.argmin(dist_to_side)
                    side_1_1_len, side_1_2_len = len(self.side_line[str(min_ind[0]) + '#1'].side_stations), \
                                                 len(self.side_line[str(min_ind[0]) + '#2'].side_stations)
                    side_2_1_len, side_2_2_len = len(self.side_line[str(min_ind[1]) + '#1'].side_stations), \
                                                 len(self.side_line[str(min_ind[1]) + '#2'].side_stations)
                    if min_side_ind < side_1_1_len:
                        up_loc = str(min_ind[0]) + '#1#' + str(min_side_ind + 1)
                    elif min_side_ind < side_1_1_len + side_1_2_len:
                        up_loc = str(min_ind[0]) + '#2#' + str(min_side_ind + 1 - side_1_1_len)
                    elif min_side_ind < side_1_1_len + side_1_2_len + side_2_1_len:
                        up_loc = str(min_ind[1]) + '#1#' + str(min_side_ind + 1 - side_1_1_len - side_1_2_len)
                    elif min_side_ind < side_1_1_len + side_1_2_len + side_2_1_len + side_2_2_len:
                        up_loc = str(min_ind[1]) + '#2#' + str(min_side_ind + 1 - side_1_1_len - side_1_2_len - side_2_1_len)
                    elif min_side_ind < side_1_1_len + side_1_2_len + side_2_1_len + side_2_2_len + 1:
                        up_loc = min_ind[0]
                    else:
                        up_loc = min_ind[1]

                # down location
                if (down_lat, down_lon) in self.loc_list:
                    down_station = self.loc_list.index((down_lat, down_lon)) + 1
                    dist_to_side = []
                    for side in [1, 2]:
                        for side_id in range(1,
                                             len(self.side_line[str(down_station) + '#' + str(side)].side_stations) + 1):
                            side_lat, side_lon = \
                                self.side_line[str(down_station) + '#' + str(side)].side_stations[side_id]['lat'], \
                                self.side_line[str(down_station) + '#' + str(side)].side_stations[side_id]['lon']
                            dist_to_side.append(get_distance(lat1=fin_lat, lon1=fin_lon, lat2=side_lat, lon2=side_lon))
                    dist_to_side.append(get_distance(lat1=fin_lat, lon1=fin_lon, lat2=down_lat, lon2=down_lon))
                    min_ind = np.argmin(dist_to_side)
                    side_1_len, side_2_len = len(self.side_line[str(down_station) + '#1'].side_stations), \
                                             len(self.side_line[str(down_station) + '#2'].side_stations)
                    if min_ind < side_1_len:
                        down_loc = str(down_station) + '#1#' + str(min_ind + 1)
                    elif min_ind < side_1_len + side_2_len:
                        down_loc = str(down_station) + '#2#' + str(min_ind + 1 - side_1_len)
                    else:
                        down_loc = down_station
                else:
                    logging.info('main stations has changed.')
                    main_station_dist = []
                    for main_station_pos in self.loc_list:
                        main_station_dist.append(
                            get_distance(lat1=ori_lat, lon1=ori_lon, lat2=main_station_pos[0], lon2=main_station_pos[1])
                        )
                    min_two = heapq.nsmallest(2, main_station_dist)
                    min_ind = [main_station_dist.index(i) + 1 for i in min_two]
                    dist_to_side = []
                    for main_station in min_ind:
                        for side in [1, 2]:
                            for side_id in range(1,
                                                 len(self.side_line[
                                                         str(main_station) + '#' + str(side)].side_stations) + 1):
                                side_lat, side_lon = \
                                    self.side_line[str(main_station) + '#' + str(side)].side_stations[side_id]['lat'], \
                                    self.side_line[str(main_station) + '#' + str(side)].side_stations[side_id]['lon']
                                dist_to_side.append(
                                    get_distance(lat1=fin_lat, lon1=fin_lon, lat2=side_lat, lon2=side_lon))
                    main_lat_1, main_lon_1 = self.loc_list[min_ind[0] - 1]
                    main_lat_2, main_lon_2 = self.loc_list[min_ind[1] - 1]
                    dist_to_side.append(get_distance(lat1=fin_lat, lon1=fin_lon, lat2=main_lat_1, lon2=main_lon_1))
                    dist_to_side.append(get_distance(lat1=fin_lat, lon1=fin_lon, lat2=main_lat_2, lon2=main_lon_2))
                    min_side_ind = np.argmin(dist_to_side)
                    side_1_1_len, side_1_2_len = len(self.side_line[str(min_ind[0]) + '#1'].side_stations), \
                                                 len(self.side_line[str(min_ind[0]) + '#2'].side_stations)
                    side_2_1_len, side_2_2_len = len(self.side_line[str(min_ind[1]) + '#1'].side_stations), \
                                                 len(self.side_line[str(min_ind[1]) + '#2'].side_stations)
                    if min_side_ind < side_1_1_len:
                        down_loc = str(min_ind[0]) + '#1#' + str(min_side_ind + 1)
                    elif min_side_ind < side_1_1_len + side_1_2_len:
                        down_loc = str(min_ind[0]) + '#2#' + str(min_side_ind + 1 - side_1_1_len)
                    elif min_side_ind < side_1_1_len + side_1_2_len + side_2_1_len:
                        down_loc = str(min_ind[1]) + '#1#' + str(min_side_ind + 1 - side_1_1_len - side_1_2_len)
                    elif min_side_ind < side_1_1_len + side_1_2_len + side_2_1_len + side_2_2_len:
                        down_loc = str(min_ind[1]) + '#2#' + str(min_side_ind + 1 - side_1_1_len - side_1_2_len - side_2_1_len)
                    elif min_side_ind < side_1_1_len + side_1_2_len + side_2_1_len + side_2_2_len + 1:
                        down_loc = min_ind[0]
                    else:
                        down_loc = min_ind[1]

            s_pos_l.append((ori_lat, ori_lon))
            s_t_l.append(up_t)
            s_loc_l.append(up_loc)
            e_loc_l.append(down_loc)
            e_pos_l.append((fin_lat, fin_lon))

        pass_df = pd.DataFrame({
            'start_pos': s_pos_l,
            'arrive_t': s_t_l,
            'start_loc': s_loc_l,
            'end_loc': e_loc_l,
            'end_pos': e_pos_l,
        })
        pass_df = pass_df.sort_values(by=['arrive_t'], ascending=[True]).reset_index(drop=True)
        return pass_df

    def get_random_t(self):
        """返回在站点的随机等待时间，服从均匀分布"""
        return np.random.randint(0, self.max_wait_t)

    @staticmethod
    def get_random_pos(cen_lat, cen_lon):
        """以站点为中心随机生成在 bbxbb 的区域内的坐标"""
        lat_diff, lon_diff = 0.00584909, 0.00898311  # 允许的范围波动
        return cen_lat + np.random.uniform(-1, 1) * lat_diff, cen_lon + np.random.uniform(-1, 1) * lon_diff


class SideLine:
    sep_num = 5  # 支线分段数，分成sep_num-1段，即sep_num个点（包含起终点）

    def __init__(self, start_lat: float, start_lon: float, end_lat: float, end_lon: float,
                 main_id: int, main_speed_list: list):
        """
        支线信息

        :param start_lat: 起点经度
        :param start_lon: 起点纬度
        :param end_lat: 终点经度
        :param end_lon: 终点纬度
        :param main_id: 主线编号
        :param main_speed_list: 各站点区间速度
        """
        self.start_lat = start_lat
        self.start_lon = start_lon
        self.end_lat = end_lat
        self.end_lon = end_lon

        lat_space = np.linspace(start_lat, end_lat, num=self.sep_num, endpoint=True)
        lon_space = np.linspace(start_lon, end_lon, num=self.sep_num, endpoint=True)

        self.side_stations = {
            i: {'lat': lat_space[i], 'lon': lon_space[i], 'pool': []}
            for i in range(1, self.sep_num)
        }

        self.dist_list = [
            get_distance(
                lat1=start_lat, lon1=start_lon, lat2=self.side_stations[1]['lat'], lon2=self.side_stations[1]['lon']
            ) if i == 0 else
            get_distance(
                lat1=self.side_stations[i]['lat'], lon1=self.side_stations[i]['lon'], lat2=self.side_stations[i+1]['lat'], lon2=self.side_stations[i+1]['lon']
            ) for i in range(self.sep_num-1)
        ]

        self.time_list = [
            (get_distance(
                lat1=start_lat, lon1=start_lon, lat2=self.side_stations[1]['lat'], lon2=self.side_stations[1]['lon']
            ) - DIS_FIX) / main_speed_list[main_id-1] if i == 0 else
            (get_distance(
                lat1=self.side_stations[i]['lat'], lon1=self.side_stations[i]['lon'], lat2=self.side_stations[i+1]['lat'], lon2=self.side_stations[i+1]['lon']
            ) - DIS_FIX) / main_speed_list[main_id-1] for i in range(self.sep_num-1)
        ]


if __name__ == '__main__':
    import sys

    sys.path.append(r"D:\mofangbus\busimulator")

    TEST_LINE = '810'
    DIRECTION = 0
    # read files
    dist_mat = pd.read_csv(rf'..\data\line_{TEST_LINE}\distance_matrix_{DIRECTION}.csv', encoding='gbk')
    speed_df = pd.read_csv(rf'..\data\line_{TEST_LINE}\speed_list_{DIRECTION}.csv', encoding='gbk')
    station_info = pd.read_csv(rf'..\data\line_{TEST_LINE}\station_info.csv', encoding='gbk')
    side_line_info = pd.read_csv(rf'..\data\line_{TEST_LINE}\side_line_info_{DIRECTION}.csv', encoding='gbk')
    # get station list
    station_list = list(station_info[station_info['direction'] == DIRECTION]['station'])
    dist_list = list(dist_mat['dist'])
    speed_list = list(speed_df['speed'])
    loc_list = list(zip(list(station_info['lat']), list(station_info['lon'])))

    test = Line(
        direc=DIRECTION, station_list=station_list, loc_list=loc_list,
        dist_list=dist_list, speed_list=speed_list, mode='multi', side_line_info=side_line_info)
