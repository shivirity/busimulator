import logging
import time
import numpy as np
import pandas as pd

from consts import *

from env.bus import Bus
from env.line import Line
from env.passenger import Passenger

from dep_decide import dep_decider
from route_decide import route_decider

logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')


def read_in():
    # read files
    dist_mat = pd.read_csv(rf'data\line_{TEST_LINE}\distance_matrix_{DIRECTION}.csv', encoding='gbk')
    speed_df = pd.read_csv(rf'data\line_{TEST_LINE}\speed_list_{DIRECTION}.csv', encoding='gbk')
    station_info = pd.read_csv(rf'data\line_{TEST_LINE}\station_info.csv', encoding='gbk')
    dep_duration_list = pd.read_csv(rf'data\line_{TEST_LINE}\dep_duration_{DIRECTION}.csv', encoding='gbk')
    dep_num_list = pd.read_csv(rf'data\line_{TEST_LINE}\dep_num_{DIRECTION}.csv', encoding='gbk')
    station_info = station_info[station_info['direction'] == DIRECTION].reset_index(drop=True)
    # get station list
    station_list = list(station_info['station'])
    dist_list = list(dist_mat['dist'])
    speed_list = list(speed_df['speed'])
    loc_list = list(zip(list(station_info['lat']), list(station_info['lon'])))
    dep_duration_list = list(dep_duration_list['dep_duration'])
    dep_num_list = list(dep_num_list['dep_num'])

    return {
        'station_list': station_list,
        'dist_list': dist_list,
        'loc_list': loc_list,
        'speed_list': speed_list,
        'dep_duration_list': dep_duration_list,
        'dep_num_list': dep_num_list,
    }


def read_in_for_opt():
    # read files
    dist_mat = pd.read_csv(rf'..\data\line_{TEST_LINE}\distance_matrix_{DIRECTION}.csv', encoding='gbk')
    speed_df = pd.read_csv(rf'..\data\line_{TEST_LINE}\speed_list_{DIRECTION}.csv', encoding='gbk')
    station_info = pd.read_csv(rf'..\data\line_{TEST_LINE}\station_info.csv', encoding='gbk')
    station_info = station_info[station_info['direction'] == DIRECTION].reset_index(drop=True)
    # get station list
    station_list = list(station_info['station'])
    dist_list = list(dist_mat['dist'])
    speed_list = list(speed_df['speed'])
    loc_list = list(zip(list(station_info['lat']), list(station_info['lon'])))

    return {
        'station_list': station_list,
        'dist_list': dist_list,
        'loc_list': loc_list,
        'speed_list': speed_list,
    }


class Sim:

    def __init__(self, station_list: list, dist_list: list, loc_list: list,
                 speed_list: list, sim_mode: str, dep_duration_list: list, dep_num_list: list, side_line_info=None):
        # 路线
        self.line = Line(direc=DIRECTION, station_list=station_list, loc_list=loc_list,
                         dist_list=dist_list, speed_list=speed_list, mode=sim_mode, side_line_info=side_line_info)
        self.dep_decider = dep_decider(sim_mode=sim_mode, dep_duration=dep_duration_list, dep_num=dep_num_list)
        self.route_decider = route_decider(sim_mode=sim_mode)

        # 仿真模式 in ['baseline', 'single', 'multi']
        self.sim_mode = sim_mode

        # 系统时间
        self.t = SIM_START_T

        # 存储所有已发车的 bus 和已接入系统的乘客
        self.all_buses = {}
        self.all_passengers = {}
        self.all_cabs = {}  # 记录所有cab行驶距离

        # 系统全局变量
        self.next_bus_id = 0
        self.next_cab_id = 0

        # 全局池和全局指针
        self.pas_pool = []  # 已完成的乘客池
        self.pas_idx = 0

        # 日志输出
        self.print_log = False

    @property
    def stop_time(self):
        """进站时间"""
        if self.sim_mode == 'baseline':
            if 7 * 3600 <= self.t < 9 * 3600 or 17 * 3600 <= self.t < 19 * 3600:
                return OLD_STOP_T_HIGH
            else:
                return OLD_STOP_T_NORM
        elif self.sim_mode == 'single':
            if 7 * 3600 <= self.t < 9 * 3600 or 17 * 3600 <= self.t < 19 * 3600:
                return NEW_STOP_T_HIGH
            else:
                return NEW_STOP_T_NORM
        else:
            assert False

    def run(self):

        # 第一次发车
        dep_dec, dep_cap = self.dep_decider.decide(cur_t=self.t)
        self.update_dep(dec=dep_dec, cap=dep_cap)

        while self.t < SIM_END_T or (not self.is_bus_finished() or not self.is_passenger_finished()):

            if self.t >= END_T:
                break

            if self.dep_decider.can_dep(cur_t=self.t):
                dep_dec, dep_cap = self.dep_decider.decide(cur_t=self.t)
                self.update_dep(dec=dep_dec, cap=dep_cap)

            if self.t == 36724:
                logging.debug('time debug')
            if self.all_buses[0].loc == '7@0':
                logging.debug(f'location debug at {self.t}')
            if self.t % 3600 == 0 and self.print_log:
                logging.info(f'system time: {int(self.t / 3600)}:00')

            # 更新乘客到站
            self.update_passengers()

            # 动作决策
            self.assign_action()

            # 系统步进
            self.run_step()

            # mode=single中出站后的结合/分离决策
            if self.sim_mode == 'single':
                self.assign_reorg()

            # 系统时间步进
            self.t += MIN_STEP

    def update_passengers(self):
        """更新乘客到站"""
        while self.pas_idx < self.line.passenger_pool.shape[0]:
            if self.line.passenger_pool.loc[self.pas_idx, 'arrive_t'] <= self.t:
                pas = Passenger(
                    pas_id=self.pas_idx,
                    start_pos=self.line.passenger_pool.loc[self.pas_idx, 'start_pos'],
                    start_loc=self.line.passenger_pool.loc[self.pas_idx, 'start_loc'],
                    arrive_time=self.line.passenger_pool.loc[self.pas_idx, 'arrive_t'],
                    end_pos=self.line.passenger_pool.loc[self.pas_idx, 'end_pos'],
                    end_loc=self.line.passenger_pool.loc[self.pas_idx, 'end_loc']
                )
                self.line.main_line[pas.start_loc].append(pas)
                self.all_passengers[self.pas_idx] = pas
            else:
                break
            self.pas_idx += 1

    def assign_action(self):
        """分配动作"""
        if self.sim_mode == 'baseline':
            dec_order = self.get_dec_order()
            for bus_id in dec_order:
                if self.route_decider.time2dec(loc=self.all_buses[bus_id].loc, state=self.all_buses[bus_id].is_waiting):
                    bus_dec = self.route_decider.decide_stop_action_baseline(
                        cur_bus=self.all_buses[bus_id], line=self.line
                    )
                    self.apply_action_in_assign_baseline(bus_id=bus_id, bus_dec=bus_dec)
        elif self.sim_mode == 'single':
            loc_dict = self.get_loc_dict()  # 只选择able=True的车辆
            for loc in loc_dict.keys():
                if loc.endswith('@0'):
                    group = list(loc_dict[loc])
                    if len(group) > 0:
                        bus_stop_dec = self.route_decider.decide_stop_action_single(
                            bus_group=group, bus_info=self.all_buses, line=self.line
                        )
                        self.apply_action_in_assign_single(bus_stop_dec=bus_stop_dec)

    def run_step(self):
        available_bus = [b.bus_id for b in self.all_buses.values() if (b.state != 'end') and (b.able is True)]
        if self.sim_mode == 'baseline':
            for bus_id in available_bus:
                cur_bus = self.all_buses[bus_id]
                loc_1, loc_2 = cur_bus.loc.split('@')
                if loc_2 == '5':
                    assert cur_bus.run_next.split('@')[1] == '0' and cur_bus.running is True
                    if cur_bus.time_count > MIN_STEP:
                        cur_bus.time_count -= MIN_STEP
                    elif 0 < cur_bus.time_count <= MIN_STEP:  # arrive at station
                        cur_bus.time_count = 0
                        cur_bus.loc = str(int(loc_1) + 1) + '@0'
                        cur_bus.run_next = str(int(loc_1) + 1) + '@5'  # end - '{max_station_num}@5'
                else:  # loc_2 == '0'
                    if cur_bus.to_stop is True:
                        assert cur_bus.stop_count > 0
                        if cur_bus.is_waiting is False:
                            cur_bus.is_waiting = True
                        cur_bus.stop_count -= MIN_STEP
                        if cur_bus.stop_count <= 0:
                            cur_bus.stop_count = 0
                            # 下车
                            bus_pas_list = [i for j in cur_bus.pass_list for i in j]
                            stay_pas_list = [pas.pas_id for pas in bus_pas_list if pas.end_loc != int(loc_1)]
                            for pas in stay_pas_list:
                                self.all_passengers[pas].add_bus_wait(seconds=self.stop_time)
                            pas_list = [pas.pas_id for pas in bus_pas_list if pas.end_loc == int(loc_1)]
                            for pas in pas_list:
                                self.all_passengers[pas].down_t = self.t
                                self.pas_pool.append(self.all_passengers[pas])
                                cur_bus.pass_list[0].remove(self.all_passengers[pas])
                            # 上车
                            pas_list = [pas.pas_id for pas in self.line.main_line[int(loc_1)]]
                            for pas in pas_list:
                                self.all_passengers[pas].on_t = self.t
                                cur_bus.pass_list[0].append(self.all_passengers[pas])
                                self.line.main_line[int(loc_1)].remove(self.all_passengers[pas])
                            # 下一站
                            if int(loc_1) == self.line.max_station_num:
                                cur_bus.state = 'end'
                                assert cur_bus.pass_num == 0
                                for cab in cur_bus.cab_id:
                                    self.all_cabs[cab]['end_t'] = self.t
                            else:
                                cur_bus.is_waiting, cur_bus.to_stop, cur_bus.stop_count = False, False, 0
                                cur_bus.loc, cur_bus.run_next = loc_1 + '@5', str(int(loc_1) + 1) + '@0'
                                cur_bus.running = True
                                cur_bus.time_count = int(
                                    (self.line.dist_list[int(loc_1) - 1] - DIS_FIX) / self.line.speed_list[
                                        int(loc_1) - 1]) + 1
                                for cab in cur_bus.cab_id:
                                    self.all_cabs[cab]['dist'] += self.line.dist_list[int(loc_1) - 1]  # 记录累计距离
                                # record number of passengers
                                for k in range(len(cur_bus.cab_id)):
                                    self.all_cabs[cur_bus.cab_id[k]]['dep_time'].append(self.t)  # 出站时间记录
                                    self.all_cabs[cur_bus.cab_id[k]]['pas_num'].append(len(cur_bus.pass_list[k]))
                        else:
                            pass
                    else:
                        assert cur_bus.running is True or cur_bus.loc.split('@')[0] == '1'
                        if int(loc_1) == self.line.max_station_num:
                            cur_bus.state = 'end'
                            assert cur_bus.pass_num == 0
                            for cab in cur_bus.cab_id:
                                self.all_cabs[cab]['end_t'] = self.t
                        else:
                            cur_bus.loc, cur_bus.run_next = loc_1 + '@5', str(int(loc_1) + 1) + '@0'
                            cur_bus.running = True
                            cur_bus.time_count = int(
                                (self.line.dist_list[int(loc_1) - 1] - DIS_FIX) / self.line.speed_list[
                                    int(loc_1) - 1])
                            for cab in cur_bus.cab_id:
                                self.all_cabs[cab]['dist'] += self.line.dist_list[int(loc_1) - 1]  # 记录累计距离
                            # record number of passengers
                            for k in range(len(cur_bus.cab_id)):
                                self.all_cabs[cur_bus.cab_id[k]]['dep_time'].append(self.t)
                                self.all_cabs[cur_bus.cab_id[k]]['pas_num'].append(len(cur_bus.pass_list[k]))

        elif self.sim_mode == 'single':
            have_decided_list = []
            for bus_id in available_bus:
                if bus_id in have_decided_list:
                    continue
                else:
                    cur_bus = self.all_buses[bus_id]
                    loc_1, loc_2 = cur_bus.loc.split('@')
                    if loc_2 == '5':
                        assert cur_bus.run_next.split('@')[1] == '0' and cur_bus.running is True
                        if cur_bus.sep_dec is not None:
                            assert cur_bus.comb_dec is None and cur_bus.time_count > 0
                            cur_bus.time_count = int(
                                SEP_DURATION +
                                (self.line.dist_list[int(loc_1) - 1] - DIS_FIX - SEP_DIST) /
                                self.line.speed_list[int(loc_1) - 1]) + 1
                            cur_bus.sep_state = cur_bus.sep_dec
                            cur_bus.sep_dec = None
                            cur_bus.time_count -= MIN_STEP
                        elif cur_bus.comb_dec is not None:
                            comb_bus_id, comb_order = cur_bus.comb_dec
                            comb_bus = self.all_buses[comb_bus_id]
                            res_time_count = int(
                                COMB_DURATION + (self.line.dist_list[int(loc_1) - 1] - DIS_FIX - COMB_DIST) /
                                self.line.speed_list[int(loc_1) - 1]) + 1

                            cur_bus.time_count = res_time_count
                            comb_bus.time_count = res_time_count
                            cur_bus.comb_state, comb_bus.comb_state = list(cur_bus.comb_dec), list(comb_bus.comb_dec)
                            cur_bus.comb_dec, comb_bus.comb_dec = None, None

                            have_decided_list.append(cur_bus.bus_id)
                            have_decided_list.append(comb_bus_id)
                            cur_bus.time_count -= MIN_STEP
                            comb_bus.time_count -= MIN_STEP
                            assert cur_bus.time_count > MIN_STEP and comb_bus.time_count > MIN_STEP

                        elif cur_bus.time_count > MIN_STEP:
                            cur_bus.time_count -= MIN_STEP

                        else:  # cur_bus.time_count -> 0
                            assert 0 < cur_bus.time_count <= MIN_STEP
                            cur_bus.time_count = 0
                            if cur_bus.sep_state is not None:
                                new_bus_front = Bus(
                                    cab_num=cur_bus.cab_num - cur_bus.sep_state,
                                    max_num_list=[SMALL_CAB for _ in range(cur_bus.cab_num - cur_bus.sep_state)],
                                    cab_id=list(cur_bus.cab_id[:(cur_bus.cab_num - cur_bus.sep_state)]),
                                    bus_id=self.next_bus_id,
                                    able=True
                                )
                                new_bus_front.pass_list = \
                                    [list(cab) for cab in cur_bus.pass_list[:(cur_bus.cab_num - cur_bus.sep_state)]]
                                self.all_buses[self.next_bus_id] = new_bus_front
                                new_bus_rear = Bus(
                                    cab_num=cur_bus.sep_state,
                                    max_num_list=[SMALL_CAB for _ in range(cur_bus.sep_state)],
                                    cab_id=list(cur_bus.cab_id[-cur_bus.sep_state:]),
                                    bus_id=self.next_bus_id + 1,
                                    able=True
                                )
                                new_bus_rear.pass_list = [list(cab) for cab in cur_bus.pass_list[-cur_bus.sep_state:]]
                                '''
                                if self.print_log:
                                    logging.info(f'{cur_bus} successfully divide into '
                                                 f'{new_bus_front} and {new_bus_rear} after station {int(loc_1)}')
                                '''
                                self.all_buses[self.next_bus_id + 1] = new_bus_rear
                                self.next_bus_id += 2
                                cur_bus.able = False
                                cur_bus.new_bus = [new_bus_front.bus_id, new_bus_rear.bus_id]
                                new_bus_front.running, new_bus_rear.running = True, True
                                new_bus_front.loc, new_bus_rear.loc = \
                                    str(int(loc_1) + 1) + '@0', str(int(loc_1) + 1) + '@0'
                                new_bus_front.run_next, new_bus_rear.run_next = \
                                    str(int(loc_1) + 1) + '@5', str(int(loc_1) + 1) + '@5'

                                for cab in new_bus_front.cab_id:
                                    self.all_cabs[cab]['dist'] += self.line.dist_list[int(loc_1) - 2]  # 记录累计距离
                                for cab in new_bus_rear.cab_id:
                                    self.all_cabs[cab]['dist'] += self.line.dist_list[int(loc_1) - 2]  # 记录累计距离

                                new_bus_front.sort_passengers(station=int(loc_1), pas_info=self.all_passengers)
                                new_bus_rear.sort_passengers(station=int(loc_1), pas_info=self.all_passengers)

                            elif cur_bus.comb_state is not None:
                                comb_bus_id, comb_order = cur_bus.comb_state
                                comb_bus = self.all_buses[comb_bus_id]
                                if comb_order > 0.8:
                                    new_bus = Bus(
                                        cab_num=cur_bus.cab_num + comb_bus.cab_num,
                                        max_num_list=[SMALL_CAB for _ in range(cur_bus.cab_num + comb_bus.cab_num)],
                                        cab_id=list(comb_bus.cab_id) + list(cur_bus.cab_id),
                                        bus_id=self.next_bus_id,
                                        able=True
                                    )
                                    new_bus.pass_list = [list(cab) for cab in comb_bus.pass_list + cur_bus.pass_list]
                                else:
                                    new_bus = Bus(
                                        cab_num=cur_bus.cab_num + comb_bus.cab_num,
                                        max_num_list=[SMALL_CAB for _ in range(cur_bus.cab_num + comb_bus.cab_num)],
                                        cab_id=list(cur_bus.cab_id) + list(comb_bus.cab_id),
                                        bus_id=self.next_bus_id,
                                        able=True
                                    )
                                    new_bus.pass_list = [list(cab) for cab in cur_bus.pass_list + comb_bus.pass_list]
                                '''
                                if self.print_log:
                                    logging.info(f'{cur_bus} and {comb_bus} successfully '
                                                 f'transform to {new_bus} after station {int(loc_1)}')
                                '''
                                self.all_buses[self.next_bus_id] = new_bus
                                self.next_bus_id += 1
                                have_decided_list.append(cur_bus.bus_id)
                                have_decided_list.append(comb_bus_id)
                                cur_bus.able, comb_bus.able = False, False
                                cur_bus.new_bus, comb_bus.new_bus = new_bus.bus_id, new_bus.bus_id
                                new_bus.running = True
                                new_bus.loc, new_bus.run_next = str(int(loc_1) + 1) + '@0', str(int(loc_1) + 1) + '@5'
                                for cab in new_bus.cab_id:
                                    self.all_cabs[cab]['dist'] += self.line.dist_list[int(loc_1) - 2]  # 记录累计距离
                                new_bus.sort_passengers(station=int(loc_1), pas_info=self.all_passengers)

                            else:
                                cur_bus.loc, cur_bus.run_next = str(int(loc_1) + 1) + '@0', str(int(loc_1) + 1) + '@5'
                                for cab in cur_bus.cab_id:
                                    self.all_cabs[cab]['dist'] += self.line.dist_list[int(loc_1) - 2]  # 记录累计距离

                    else:  # loc_2 == '0'
                        if cur_bus.to_stop is True:
                            assert cur_bus.stop_count > 0
                            if cur_bus.is_waiting is False:
                                cur_bus.is_waiting = True
                            cur_bus.stop_count -= MIN_STEP
                            if cur_bus.stop_count <= 0:
                                # loc_dict = self.get_loc_dict()  # 只选择able=True的车辆
                                cur_bus.stop_count = 0  # 可能有车辆同时进站，发生在容量不足时
                                same_stop_bus = list(self.get_loc_dict()[cur_bus.loc])  # [bus_ids]
                                left_bus_list = [b for b in same_stop_bus if
                                                 b not in have_decided_list and 0 < self.all_buses[
                                                     b].stop_count <= MIN_STEP]
                                if len(left_bus_list) < 0.8:  # 只有一辆车同时停留
                                    # 下车
                                    bus_pas_list = [i for j in cur_bus.pass_list for i in j]

                                    stay_pas_list = [pas.pas_id for pas in bus_pas_list if pas.end_loc != int(loc_1)]
                                    for pas in stay_pas_list:
                                        self.all_passengers[pas].add_bus_wait(seconds=self.stop_time)

                                    pas_list = [pas.pas_id for pas in bus_pas_list if pas.end_loc == int(loc_1)]
                                    down_num = len(pas_list)
                                    for pas in pas_list:
                                        self.all_passengers[pas].down_t = self.t
                                        self.pas_pool.append(self.all_passengers[pas])
                                        for cab_list in cur_bus.pass_list:
                                            if self.all_passengers[pas] in cab_list:
                                                cab_list.remove(self.all_passengers[pas])
                                                break
                                        else:
                                            assert False, f'passenger id = {pas} not on bus id = {cur_bus.bus_id}'
                                    # 上车
                                    on_num = 0  # 上车多少人
                                    while cur_bus.pass_num < cur_bus.max_num and \
                                            len(self.line.main_line[int(loc_1)]) > 0:
                                        on_pas = self.line.main_line[int(loc_1)].pop(0)
                                        on_pas.on_t = self.t
                                        cur_bus.get_on(pas=on_pas)
                                        on_num += 1
                                    assert len(self.line.main_line[int(loc_1)]) == 0 or \
                                           cur_bus.pass_num == cur_bus.max_num, f'{len(self.line.main_line[int(loc_1)])}'
                                    if down_num + on_num < 0.2:
                                        # assert cur_bus.pass_num == cur_bus.max_num
                                        if self.print_log:
                                            logging.error(f'nobody gets on or off at station={loc_1} at {self.t}')
                                    have_decided_list.append(cur_bus.bus_id)
                                    # 下一站
                                    if int(loc_1) == self.line.max_station_num:
                                        cur_bus.state = 'end'
                                        assert cur_bus.pass_num == 0
                                        for cab in cur_bus.cab_id:
                                            self.all_cabs[cab]['end_t'] = self.t
                                    else:
                                        cur_bus.is_waiting, cur_bus.to_stop = False, False
                                        cur_bus.running, cur_bus.to_dec_trans, cur_bus.stop_count = True, True, 0
                                        cur_bus.loc, cur_bus.run_next = loc_1 + '@5', str(int(loc_1) + 1) + '@0'
                                        cur_bus.time_count = int(
                                            (self.line.dist_list[int(loc_1) - 1] - DIS_FIX) / self.line.speed_list[
                                                int(loc_1) - 1]) + 1

                                        # record number of passengers on current bus
                                        for k in range(len(cur_bus.cab_id)):
                                            self.all_cabs[cur_bus.cab_id[k]]['dep_time'].append(self.t)
                                            self.all_cabs[cur_bus.cab_id[k]]['pas_num'].append(
                                                len(cur_bus.pass_list[k])
                                            )

                                    cur_bus.sort_passengers(
                                        station=int(loc_1), pas_info=self.all_passengers, num_behind=1
                                    )

                                else:  # 多辆车同时停留
                                    for left_bus in left_bus_list:
                                        assert self.all_buses[left_bus].is_waiting is True
                                        self.all_buses[left_bus].stop_count -= MIN_STEP
                                    dec_list = list(left_bus_list)
                                    dec_list.append(bus_id)
                                    # 下车
                                    down_num_list = []  # 每辆车下车多少人
                                    for dec_bus in dec_list:
                                        bus_pas_list = [i for j in self.all_buses[dec_bus].pass_list for i in j]

                                        stay_pas_list = [pas.pas_id for pas in bus_pas_list if
                                                         pas.end_loc != int(loc_1)]
                                        for pas in stay_pas_list:
                                            self.all_passengers[pas].add_bus_wait(seconds=self.stop_time)

                                        pas_list = [pas.pas_id for pas in bus_pas_list if pas.end_loc == int(loc_1)]
                                        down_num_list.append(len(pas_list))
                                        for pas in pas_list:
                                            self.all_passengers[pas].down_t = self.t
                                            self.pas_pool.append(self.all_passengers[pas])
                                            for cab_list in self.all_buses[dec_bus].pass_list:
                                                if self.all_passengers[pas] in cab_list:
                                                    cab_list.remove(self.all_passengers[pas])
                                                    break
                                            else:
                                                assert False, f'passenger id = {pas} not on bus id = {dec_bus}'
                                    # 上车
                                    on_num_list = [0 for _ in dec_list]  # 每辆车上车多少人
                                    # pas_list = [pas.pas_id for pas in self.line.main_line[int(loc_1)]]
                                    pas_cap_list = [self.all_buses[bus].max_num - self.all_buses[bus].pass_num
                                                    for bus in dec_list]
                                    on_order = sorted(dec_list,
                                                      key=lambda x: pas_cap_list[dec_list.index(x)],
                                                      reverse=True
                                                      )
                                    for on_bus in on_order:
                                        while self.all_buses[on_bus].pass_num < self.all_buses[on_bus].max_num and \
                                                len(self.line.main_line[int(loc_1)]) > 0:
                                            on_pas = self.line.main_line[int(loc_1)].pop(0)
                                            on_pas.on_t = self.t
                                            self.all_buses[on_bus].get_on(pas=on_pas)
                                            on_num_list[dec_list.index(on_bus)] += 1
                                    assert not self.line.main_line[int(loc_1)] or \
                                           sum([self.all_buses[on_bus].max_num - self.all_buses[on_bus].pass_num for
                                                on_bus in on_order]) == 0, f'{int(loc_1)}'
                                    for ind in range(len(down_num_list)):
                                        if down_num_list[ind] + on_num_list[ind] < 0.2:
                                            assert \
                                                self.all_buses[dec_list[ind]].pass_num == self.all_buses[
                                                    dec_list[ind]].max_num or len(self.line.main_line[int(loc_1)]) == 0
                                            if self.print_log:
                                                logging.error(f'nobody gets on or off at station={loc_1} at {self.t}')
                                        # 下一站
                                        sel_bus = self.all_buses[dec_list[ind]]
                                        if int(loc_1) == self.line.max_station_num:
                                            sel_bus.state = 'end'
                                            assert cur_bus.pass_num == 0
                                            for cab in sel_bus.cab_id:
                                                self.all_cabs[cab]['end_t'] = self.t
                                        else:
                                            sel_bus.is_waiting, sel_bus.to_stop = False, False
                                            sel_bus.running, sel_bus.to_dec_trans, sel_bus.stop_count = True, True, 0
                                            sel_bus.loc, sel_bus.run_next = loc_1 + '@5', str(int(loc_1) + 1) + '@0'
                                            sel_bus.time_count = int(
                                                (self.line.dist_list[int(loc_1) - 1] - DIS_FIX) / self.line.speed_list[
                                                    int(loc_1) - 1]) + 1

                                            # record number of passengers on selected bus
                                            for k in range(len(sel_bus.cab_id)):
                                                self.all_cabs[sel_bus.cab_id[k]]['dep_time'].append(self.t)
                                                self.all_cabs[sel_bus.cab_id[k]]['pas_num'].append(
                                                    len(sel_bus.pass_list[k])
                                                )

                                        sel_bus.sort_passengers(
                                            station=int(loc_1), pas_info=self.all_passengers, num_behind=1
                                        )
                                        have_decided_list.append(dec_list[ind])
                            else:
                                pass

                        else:  # 在站点不停留
                            assert cur_bus.running is True or cur_bus.loc.split('@')[0] == '1'
                            if int(loc_1) == self.line.max_station_num:
                                cur_bus.state = 'end'
                                assert cur_bus.pass_num == 0
                                for cab in cur_bus.cab_id:
                                    self.all_cabs[cab]['end_t'] = self.t
                            else:
                                cur_bus.loc, cur_bus.run_next = loc_1 + '@5', str(int(loc_1) + 1) + '@0'
                                cur_bus.running, cur_bus.to_dec_trans = True, True
                                cur_bus.time_count = int(
                                    (self.line.dist_list[int(loc_1) - 1] - DIS_FIX) / self.line.speed_list[
                                        int(loc_1) - 1])

                                # record number of passengers on current bus (without stopping)
                                for k in range(len(cur_bus.cab_id)):
                                    self.all_cabs[cur_bus.cab_id[k]]['dep_time'].append(self.t)
                                    self.all_cabs[cur_bus.cab_id[k]]['pas_num'].append(
                                        len(cur_bus.pass_list[k])
                                    )

                                cur_bus.sort_passengers(station=int(loc_1), pas_info=self.all_passengers)

    def assign_reorg(self):
        """结合和分离决策(mode='single')"""
        assert self.sim_mode == 'single'
        available_bus = [b.bus_id for b in self.all_buses.values() if (b.state != 'end') and (b.able is True)]
        for bus in available_bus:
            cur_bus = self.all_buses[bus]
            if cur_bus.to_dec_trans is True:
                # 分离决策
                if cur_bus.cab_num > 1.8:  # 超过2节车厢
                    cur_station = int(cur_bus.loc.split('@')[0])
                    next_down_num = cur_bus.stop_pass_num(station=cur_station + 1)
                    if next_down_num > MIN_SEP_PASS_NUM:  # 下站下车人数到达下限
                        not_down_num = cur_bus.pass_num - next_down_num
                        if not_down_num * self.stop_time >= \
                                SEP_DURATION - SEP_DIST / self.line.speed_list[cur_station - 1]:  # 不下车乘客时间节约效果
                            sep_cab_num = int(next_down_num / cur_bus.max_num_list[0]) + 1
                            cur_bus.sep_dec = sep_cab_num if sep_cab_num < cur_bus.cab_num else int(cur_bus.cab_num - 1)
                        else:
                            pass
                    else:
                        pass
                else:
                    pass
                # 结合决策
                if cur_bus.sep_dec is None:
                    loc_dict = self.get_loc_dict()
                    cur_station = int(cur_bus.loc.split('@')[0])
                    # 不同时sep和comb
                    pot_comb_buses = [b for b in loc_dict[cur_bus.loc] if
                                      (self.all_buses[b].sep_dec is None) and (self.all_buses[b].comb_dec is None)]
                    pot_comb_order = sorted(pot_comb_buses, key=lambda x: self.all_buses[x].time_count, reverse=True)
                    for pot_bus in pot_comb_order:
                        if cur_bus.cab_num + self.all_buses[pot_bus].cab_num > 3.2:
                            pass
                        else:
                            # condition1: enough distance to cover
                            if self.all_buses[pot_bus].time_count < COMB_DIST / self.line.speed_list[cur_station - 1] + \
                                    (1 - RATE_COMB_ROUTE) * \
                                    ((self.line.dist_list[cur_station - 1] - COMB_DIST) / self.line.speed_list[
                                        cur_station - 1]):
                                # condition2: much to get off in the front bus
                                # 在下一站点下车的乘客数量
                                next_n_down_num = self.all_buses[pot_bus].get_off_pas_num(
                                    s_station=cur_station + 2, e_station=cur_station + COMB_FORE_STA)
                                if self.all_buses[pot_bus].pass_num == 0 or \
                                        next_n_down_num / self.all_buses[pot_bus].pass_num >= RATE_FRONT_PASS:
                                    # condition3: much to stay on the rear bus
                                    next_n_down_num = cur_bus.get_off_pas_num(
                                        s_station=cur_station + COMB_FORE_STA, e_station=self.line.max_station_num)
                                    if self.all_buses[pot_bus].pass_num == 0 or \
                                            next_n_down_num / self.all_buses[pot_bus].pass_num >= RATE_REAR_PASS:
                                        self.all_buses[pot_bus].comb_dec = [cur_bus.bus_id, 0]
                                        cur_bus.comb_dec = [pot_bus, 1]
                                        break
                                    else:
                                        pass
                                else:
                                    pass
                            else:
                                pass
                cur_bus.to_dec_trans = False
            else:
                pass

    def get_dec_order(self):
        """决策顺序生成"""
        available_bus = [b.bus_id for b in self.all_buses.values() if (b.state != 'end') and (b.able is True)]
        return sorted(available_bus, key=lambda x: self.all_buses[x].loc_num, reverse=True)

    def get_loc_dict(self):
        """位置字典，key=loc，value=bus_id"""
        available_bus = [b.bus_id for b in self.all_buses.values() if (b.state != 'end') and (b.able is True)]
        tmp_dict = {}
        for s in range(self.line.max_station_num, 0, -1):
            for loc in ['@5', '@0']:
                tmp_dict[str(s) + loc] = [b for b in available_bus if self.all_buses[b].loc == str(s) + loc]
        return tmp_dict

    def is_bus_finished(self) -> bool:
        return len([b for b in self.all_buses.values() if (b.state != 'end') and (b.able is True)]) < 0.8

    def is_passenger_finished(self) -> bool:
        return len(self.pas_pool) == len(self.all_passengers)

    def update_dep(self, dec: int, cap: int):
        """更新最新的发车决策"""
        self.dep_decider.last_dep = self.t
        # ------------ start create new bus ----------
        cur_bus_id, cur_cab_id = self.next_bus_id, self.next_cab_id
        self.all_buses[cur_bus_id] = Bus(
            cab_num=dec, max_num_list=[cap for _ in range(dec)],
            cab_id=list(range(cur_cab_id, cur_cab_id + dec)), bus_id=cur_bus_id, able=True
        )
        for cab_id in range(cur_cab_id, cur_cab_id + dec):
            self.all_cabs[cab_id] = {
                'dist': 0,
                'start_t': self.t,
                'end_t': None,
                'arr_time': [],  # 入站时间
                'dep_time': [],  # 出站时间
                'pas_num': [],  # 乘客人数
            }  # 记录行驶距离
        self.next_bus_id += 1
        self.next_cab_id += dec
        # ------------ end create new bus ------------

    def apply_action_in_assign_baseline(self, bus_id, bus_dec):
        """执行 assign_action 中进行的决策"""
        if bus_dec['stop']:
            self.all_buses[bus_id].to_stop = True
            self.all_buses[bus_id].stop_count += self.stop_time

    def apply_action_in_assign_single(self, bus_stop_dec: dict):
        """分配车辆的停站决策"""
        for key, value in bus_stop_dec.items():
            self.all_buses[key].to_stop = value
            self.all_buses[key].stop_count += self.stop_time if value is True else 0

    def get_passenger_optimal(self):
        """获取乘客时间理论值"""
        pass_t_list = []
        for pas in self.all_passengers.values():
            start_loc, end_loc, sum_t = pas.start_loc, pas.end_loc, 0
            for loc in range(start_loc, end_loc):
                sum_t += int(self.line.dist_list[loc - 1] / self.line.speed_list[loc - 1]) + 1
            pass_t_list.append(sum_t)
        return sum(pass_t_list) / len(pass_t_list) / 60

    def get_statistics(self):
        """获取系统表现统计数据"""
        # 乘客统计数据

        if None in [val.down_t for val in self.all_passengers.values()]:
            # assert False, \
            # f'some passengers not get on/off, {self.dep_decider.dep_num_list, self.dep_decider.dep_duration_list}'
            return {
                'power consumption(condition, kWh)': 500000000,
                'avg_travel_t(on bus, min)': 37,
                'avg_travel_t(full, min)': 7,
            }

        else:
            avg_travel_t, avg_wait_t, full_t, avg_station_wait_t = 0, 0, 0, 0
            for pas in self.all_passengers.values():
                pas.get_statistics(loc_list=self.line.loc_list)
                avg_travel_t += pas.travel_t
                avg_wait_t += pas.bus_wait_t
                full_t += pas.full_jour_t
                avg_station_wait_t += pas.station_wait_t
            avg_travel_t /= (len(self.all_passengers) * 60)
            avg_wait_t /= (len(self.all_passengers) * 60)
            full_t /= (len(self.all_passengers) * 60)
            avg_station_wait_t /= (len(self.all_passengers) * 60)

            # 车辆出行数据
            if self.sim_mode == 'baseline':
                cap = LARGE_BUS
                # 能耗
                power_consump_speed = sum([cab['dist'] for cab in self.all_cabs.values()]) * CONSUMP_SPEED_OLD
                power_consump_cond = sum([cab['dist'] for cab in self.all_cabs.values()]) * CONSUMP_CONDITION_OLD
                # 乘客数量
                avg_pas_num_list = [sum(cab['pas_num']) / len(cab['pas_num']) for cab in self.all_cabs.values()]
                avg_pas_num = np.mean(avg_pas_num_list) / cap
                pas_num_list = [max(cab['pas_num']) for cab in self.all_cabs.values()]
                max_pas_num = np.max(pas_num_list) / cap
                avg_pas_num_list_early = [sum(cab['pas_num']) / len(cab['pas_num']) for cab in self.all_cabs.values()
                                          if 6 * 3600 <= cab['dep_time'][0] < 8 * 3600]
                avg_pas_num_early = np.mean(avg_pas_num_list_early) / cap
                avg_pas_num_list_noon = [sum(cab['pas_num']) / len(cab['pas_num']) for cab in self.all_cabs.values()
                                         if 10 * 3600 <= cab['dep_time'][0] < 12 * 3600]
                avg_pas_num_noon = np.mean(avg_pas_num_list_noon) / cap
                avg_pas_num_list_late = [sum(cab['pas_num']) / len(cab['pas_num']) for cab in self.all_cabs.values()
                                         if 16 * 3600 <= cab['dep_time'][0] < 18 * 3600]
                avg_pas_num_late = np.mean(avg_pas_num_list_late) / cap
                driver_wage = 20 * DRIVER_WAGE_OLD

            elif self.sim_mode == 'single':
                cap = SMALL_CAB
                power_consump_speed = sum([cab['dist'] for cab in self.all_cabs.values()]) * CONSUMP_SPEED_NEW
                power_consump_cond = sum([cab['dist'] for cab in self.all_cabs.values()]) * CONSUMP_CONDITION_NEW
                max_pas_num = np.max([max(cab['pas_num']) for cab in self.all_cabs.values()]) / cap
                # max_pas_num = np.max(pas_num_array)
                avg_pas_num_array = np.array([sum(cab['pas_num']) / len(cab['pas_num']) for cab in self.all_cabs.values()])
                avg_pas_num = np.mean(avg_pas_num_array) / cap
                avg_pas_num_array_early = np.array(
                    [sum(cab['pas_num']) / len(cab['pas_num']) for cab in self.all_cabs.values()
                     if 6 * 3600 <= cab['dep_time'][0] < 8 * 3600])
                avg_pas_num_early = np.mean(avg_pas_num_array_early) / cap
                avg_pas_num_array_noon = np.array(
                    [sum(cab['pas_num']) / len(cab['pas_num']) for cab in self.all_cabs.values()
                     if 10 * 3600 <= cab['dep_time'][0] < 12 * 3600])
                avg_pas_num_noon = np.mean(avg_pas_num_array_noon) / cap
                avg_pas_num_array_late = np.array(
                    [sum(cab['pas_num']) / len(cab['pas_num']) for cab in self.all_cabs.values()
                     if 16 * 3600 <= cab['dep_time'][0] < 18 * 3600])
                avg_pas_num_late = np.mean(avg_pas_num_array_late) / cap
                driver_wage = 20 * 2 * DRIVER_WAGE_NEW

            return {
                'avg_travel_t(on bus, min)': avg_travel_t,
                'avg_travel_t(full, min)': full_t,
                'avg_wait_t(min)': avg_wait_t,
                'avg_station_wait_t(min)': avg_station_wait_t,
                'power consumption(equal speed, kWh)': power_consump_speed,
                'power consumption(condition, kWh)': power_consump_cond,
                'driver wage(WRMB, year)': driver_wage / 10000,  # avg_travel_time / departure_duration = 20
                'max_pas_num': max_pas_num,
                'avg_pas_num(all day)': avg_pas_num,
                'avg_pas_num(early)': avg_pas_num_early,
                'avg_pas_num(noon)': avg_pas_num_noon,
                'avg_pas_num(late)': avg_pas_num_late,
                'carbon emission(g)': 0.31 * 0.23 * power_consump_cond
            }


if __name__ == '__main__':
    line_info = read_in()
    start = time.time()

    # debug
    # line_info['dep_num_list'] = [0, 0, 0, 0, 0, 0, 1, 1, 2, 2, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 1, 1, 1]
    # line_info['dep_duration_list'] = [0, 0, 0, 0, 0, 0, 840, 840, 900, 900, 840, 840, 840, 840, 840, 840, 840, 840, 840, 720, 720, 600, 600, 600]

    sim = Sim(**line_info, sim_mode='single')
    sim.print_log = False
    sim.run()
    sim_result = sim.get_statistics()
    print('runtime: {:.2f}s'.format((time.time() - start)))
    print(f'optimal travel time on bus: {sim.get_passenger_optimal()} min')
