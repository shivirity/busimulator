import numpy as np
from env.passenger import Passenger


def get_main_line_id(location: str):
    """获取乘客上下车地点的主线编号"""
    if isinstance(location, (int, np.integer)):
        return location
    else:
        main_id, _, __ = map(int, location.split('#'))
        return main_id


class Bus:

    def __init__(self, cab_num: int, max_num_list: list, cab_id: list, bus_id: int, able: bool,
                 start_loc: str = '1@0', start_run_next: str = '1@5'):
        self.cab_num = cab_num  # 车厢数量
        self.pass_list = [[] for _ in range(cab_num)]  # 储存乘客对象，list
        self.max_num_list = list(max_num_list)
        self.cab_id = cab_id  # 包含的 cab 编号
        self.bus_id = bus_id  # 单一 bus id

        # 可用性相关
        self.able = able
        self.new_bus = None

        # 决策过程相关
        self.to_stop = False  # 是否要在站点停留
        self.is_waiting = False  # 是否在上下客的等待过程中
        self.stop_count = 0  # 在站点剩余停留时间
        self.to_dec_trans = False  # 是否要进行结合/分离决策

        # -- 结合分离决策
        self.sep_dec = None  # None or int
        self.comb_dec = None  # None or list['bus_id', front:0/rear:1]

        # -- 结合分离决策状态变量
        self.sep_state = None  # run_step中存储sep状态的变量
        self.comb_state = None  # run_step中存储comb状态的变量

        # 主线+支线优化相关
        self.can_return_stop = False  # 是否可以从支线返回时停主线站点
        self.to_turn = 0  # 车辆转向，0表示不转向（主线），1表示转向支线1，2表示转向支线2

        # 行驶过程相关
        self.running = False  # 是否正在行驶
        self.state = 'start'  # in ['start, end']
        self.loc = start_loc  # 初始化位置在起始站点
        self.run_next = start_run_next  # 下一站点
        self.time_count = 0
        self.is_returning = False  # 是否正在返回, 用于主线+支线优化

    def __repr__(self):
        return f'bus_{self.bus_id}'

    @property
    def loc_num(self):
        """仅用于决策顺序排序使用"""
        loc_1, loc_2 = self.loc.split('@')
        return int(loc_1) + int(loc_2) / 10

    @property
    def max_num(self):
        """返回车上乘客数量上限"""
        return sum(self.max_num_list)

    @property
    def pass_num(self):
        """返回车上乘客数量"""
        return len([i for j in self.pass_list for i in j])

    def is_to_stop(self, station: int):
        """当前车辆上是否有需要下车的乘客"""
        pass_list = [i for j in self.pass_list for i in j]
        for passenger in pass_list:
            if passenger.end_loc == station:
                return True
        else:
            return False

    def stop_num_at_side_line(self, main_line_id: int) -> tuple:
        """
        返回当前车辆在支线上的下车人数

        :param main_line_id: 主线编号
        :return: 下车人数(side_1_down, side_2_down)
        """
        pass_list = [i for j in self.pass_list for i in j]
        side_1_count, side_2_count = 0, 0
        for pas in pass_list:
            if not isinstance(pas.end_loc, (int, np.integer)):
                main_id, side_id, side_order = map(int, pas.end_loc.split('#'))
                if main_id == main_line_id:
                    if side_id == 1:
                        side_1_count += 1
                    else:
                        side_2_count += 1
        return side_1_count, side_2_count

    def stop_pass_num(self, station):
        """当前车辆上在station（主线站点或主线+支线站点）需要下车的乘客数量"""
        pass_list = [i for j in self.pass_list for i in j]
        return len([0 for pas in pass_list if pas.end_loc == station])

    def sum_stations_to_go(self, station: int):
        """
        统计车上乘客剩余站点的总和

        :param station: 当前站点（主线）
        :return: 车上乘客剩余站点的总和
        """
        pass_list = [i for j in self.pass_list for i in j]
        return sum([pas.end_loc - station if isinstance(pas.end_loc, (int, np.integer))
                    else int(pas.end_loc.split('#')[0]) - station for pas in pass_list])

    def get_on(self, pas: Passenger):
        """单名乘客上车，遵循从前先后的顺序"""
        for cab in range(self.cab_num):
            if len(self.pass_list[cab]) < self.max_num_list[cab]:
                self.pass_list[cab].append(pas)
                pas.on_bus = self.bus_id
                break
        else:
            assert False, f'车辆已满，上车失败'

    def sort_passengers(self, station: int, pas_info: dict, num_behind: int = 1, mode: str = 'single'):
        """
        车上乘客重新排列，用于上下客完成后或车厢重组后乘客位置更新

        :param station: 当前站点编号
        :param pas_info: 乘客信息字典
        :param num_behind: 最后一节车厢理论容纳乘客的最大剩余站点数量
        :param mode: 仿真模式
        :return:
        """

        if mode == 'single':
            if self.cab_num == 1:
                return
            elif self.pass_num == 0:
                return
            else:
                pas_list = [i.pas_id for j in self.pass_list for i in j]
                sorted_pas_list = sorted(pas_list, key=lambda x: pas_info[x].end_loc - station, reverse=True)  # ids
                num_behind_list = [ids for ids in sorted_pas_list if pas_info[ids].end_loc - station <= num_behind]  # ids
                if len(sorted_pas_list) - len(num_behind_list) >= sum(self.max_num_list[:-1]):
                    new_pas_list, new_cab, idx = [], [], 0
                    while idx < sum(self.max_num_list[:-1]):
                        new_cab.append(pas_info[sorted_pas_list[idx]])
                        if len(new_cab) == self.max_num_list[0]:
                            new_pas_list.append(list(new_cab))
                            new_cab = []
                        idx += 1
                    new_pas_list.append([pas_info[pas] for pas in sorted_pas_list[idx:]])
                    self.pass_list = new_pas_list
                    assert len(self.pass_list) == self.cab_num, f'{len(self.pass_list)}, {self.cab_num}'
                    return
                else:
                    new_pas_list, new_cab, idx = [], [], 0
                    while idx < len(sorted_pas_list) - len(num_behind_list):
                        new_cab.append(pas_info[sorted_pas_list[idx]])
                        if len(new_cab) == self.max_num_list[0]:
                            new_pas_list.append(list(new_cab))
                            new_cab = []
                        idx += 1
                    new_pas_list.append(list(new_cab))
                    assert len(new_pas_list) <= self.cab_num - 1
                    if len(new_pas_list) < self.cab_num - 1:
                        while len(new_pas_list) < self.cab_num - 1:
                            new_pas_list.append([])
                    new_pas_list.append([pas_info[pas] for pas in num_behind_list])
                    self.pass_list = new_pas_list
                    assert len(self.pass_list) == self.cab_num, f'{self.pass_list}, {self.cab_num}'
                    return
        else:
            assert mode in ['multi', 'multi_order']
            if self.cab_num == 1:
                return
            elif self.pass_num == 0:
                return
            else:
                pas_list = [i.pas_id for j in self.pass_list for i in j]
                sorted_pas_list = sorted(pas_list, key=lambda x: get_main_line_id(location=pas_info[x].end_loc) - station, reverse=True)  # ids
                num_behind_list = [ids for ids in sorted_pas_list if
                                   get_main_line_id(location=pas_info[ids].end_loc) - station <= num_behind]  # ids
                if len(sorted_pas_list) - len(num_behind_list) >= sum(self.max_num_list[:-1]):
                    new_pas_list, new_cab, idx = [], [], 0
                    while idx < sum(self.max_num_list[:-1]):
                        new_cab.append(pas_info[sorted_pas_list[idx]])
                        if len(new_cab) == self.max_num_list[0]:
                            new_pas_list.append(list(new_cab))
                            new_cab = []
                        idx += 1
                    new_pas_list.append([pas_info[pas] for pas in sorted_pas_list[idx:]])
                    self.pass_list = new_pas_list
                    assert len(self.pass_list) == self.cab_num, f'{len(self.pass_list)}, {self.cab_num}'
                    return
                else:
                    new_pas_list, new_cab, idx = [], [], 0
                    while idx < len(sorted_pas_list) - len(num_behind_list):
                        new_cab.append(pas_info[sorted_pas_list[idx]])
                        if len(new_cab) == self.max_num_list[0]:
                            new_pas_list.append(list(new_cab))
                            new_cab = []
                        idx += 1
                    new_pas_list.append(list(new_cab))
                    assert len(new_pas_list) <= self.cab_num - 1
                    if len(new_pas_list) < self.cab_num - 1:
                        while len(new_pas_list) < self.cab_num - 1:
                            new_pas_list.append([])
                    new_pas_list.append([pas_info[pas] for pas in num_behind_list])
                    self.pass_list = new_pas_list
                    assert len(self.pass_list) == self.cab_num, f'{self.pass_list}, {self.cab_num}'
                    return

    def get_off_pas_num(self, s_station: int, e_station: int):
        """
        在s_station到e_station间下车的乘客数量（包含s_station，不包含e_station）

        :param s_station: 最近下车站点
        :param e_station: 最远下车站点
        :return: 满足条件的乘客数量(int)
        """
        pass_list = [i for j in self.pass_list for i in j]
        return len([0 for pas in pass_list
                    if (s_station <= pas.end_loc < e_station
                        if isinstance(pas.end_loc, (int, np.integer))
                        else s_station <= int(pas.end_loc.split('#')[0]) < e_station)])
