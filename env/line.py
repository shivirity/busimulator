import random
import numpy as np
import pandas as pd

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
        self.side_line_info = side_line_info

        # main_line (dict)
        self.main_line = None
        # side_line (dict)
        self.side_line = None

        # 生成主线
        self.create_main_line()
        # 生成支线
        self.create_side_line()

        # consts
        self.max_wait_t = 10 * 60

        # passenger pool
        self.passenger_pool = self.get_passenger_info()

    def create_main_line(self):
        """
        生成主线，主线上由 main_line 字典维护

        :return:
        """
        # 站点等待人
        self.main_line = {
            i: [] for i in range(1, self.max_station_num+1)
        }

    def create_side_line(self):
        # based on side_line_info
        self.side_line = None

    def get_passenger_info(self):
        """
        加载所有乘客信息, 包括起始站点和起始时间, 到达站点后 reveal
        返回包含乘客出发点、时间、原出发站点、原结束站点、结束点的 dataframe

        :return: pd.Dataframe
        """
        pass_info = pd.read_csv(r'data\line_810\chain_data.csv', encoding='utf-8')
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
            ori_lat, ori_lon = self.get_random_pos(cen_lat=up_lat, cen_lon=up_lon)
            up_loc, down_loc = self.station_list.index(up_station), self.station_list.index(down_station)
            fin_lat, fin_lon = self.get_random_pos(cen_lat=down_lat, cen_lon=down_lon)
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

    def __init__(self):
        pass


if __name__ == '__main__':

    import sys
    sys.path.append(r"D:\mofangbus\busimulator")

    TEST_LINE = '810'
    DIRECTION = 0
    # read files
    dist_mat = pd.read_csv(rf'..\data\line_{TEST_LINE}\distance_matrix_{DIRECTION}.csv', encoding='gbk')
    speed_df = pd.read_csv(rf'..\data\line_{TEST_LINE}\speed_list_{DIRECTION}.csv', encoding='gbk')
    station_info = pd.read_csv(rf'..\data\line_{TEST_LINE}\station_info.csv', encoding='gbk')
    # get station list
    station_list = list(station_info[station_info['direction'] == DIRECTION]['station'])
    dist_list = list(dist_mat['dist'])
    speed_list = list(speed_df['speed'])
    loc_list = list(zip(list(station_info['lat']), list(station_info['lon'])))

    test = Line(
        direc=DIRECTION, station_list=station_list, loc_list=loc_list,
        dist_list=dist_list, speed_list=speed_list, mode='baseline')
