import logging
import numpy as np
import pandas as pd

from consts import *

from env.bus import Bus
from env.line import Line
from env.passenger import Passenger

from dep_decide import dep_decider
from route_decide import route_decider

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def read_in():
    # read files
    dist_mat = pd.read_csv(rf'data\line_{TEST_LINE}\distance_matrix_{DIRECTION}.csv', encoding='gbk')
    speed_df = pd.read_csv(rf'data\line_{TEST_LINE}\speed_list_{DIRECTION}.csv', encoding='gbk')
    station_info = pd.read_csv(rf'data\line_{TEST_LINE}\station_info.csv', encoding='gbk')
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
                 speed_list: list, sim_mode: str, side_line_info=None):
        # 路线
        self.line = Line(direc=DIRECTION, station_list=station_list, loc_list=loc_list,
                         dist_list=dist_list, speed_list=speed_list, mode=sim_mode, side_line_info=side_line_info)
        self.dep_decider = dep_decider(sim_mode=sim_mode)
        self.route_decider = route_decider(sim_mode=sim_mode)

        # 仿真模式 in ['baseline', 'single', 'fish_bone']
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
        self.pas_pool = []
        self.pas_idx = 0

    @property
    def stop_time(self):
        """进站时间"""
        if self.sim_mode == 'baseline':
            if 7 * 3600 <= self.t < 9 * 3600 or 17 * 3600 <= self.t < 19 * 3600:
                return OLD_STOP_T_HIGH
            else:
                return OLD_STOP_T_NORM
        else:
            assert False

    def run(self):

        # 第一次发车
        dep_dec, dep_cap = self.dep_decider.decide()
        self.update_dep(dec=dep_dec, cap=dep_cap)

        while self.t < SIM_END_T or not self.is_bus_finished():

            if self.dep_decider.can_dep(cur_t=self.t):
                dep_dec, dep_cap = self.dep_decider.decide()
                self.update_dep(dec=dep_dec, cap=dep_cap)

            if self.t == 79200:
                logging.debug('here')
            if self.t % 3600 == 0:
                logging.info(f'system time: {int(self.t/3600)}:00')

            # 更新乘客到站
            self.update_passengers()

            # 动作决策
            self.assign_action()

            # 系统步进
            self.run_step()

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
        dec_order = self.get_dec_order()
        for bus_id in dec_order:
            if self.route_decider.time2dec(loc=self.all_buses[bus_id].loc, state=self.all_buses[bus_id].is_waiting):
                bus_dec = self.route_decider.decide_action(cur_bus=self.all_buses[bus_id], line=self.line)
                self.apply_action_in_assign(bus_id=bus_id, bus_dec=bus_dec)

    def run_step(self):
        available_bus = [b.bus_id for b in self.all_buses.values() if b.state != 'end']
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
                                for cab in cur_bus.cab_id:
                                    self.all_cabs[cab]['end_t'] = self.t
                            else:
                                cur_bus.is_waiting, cur_bus.to_stop, cur_bus.stop_count = False, False, 0
                                cur_bus.loc, cur_bus.run_next = loc_1 + '@5', str(int(loc_1) + 1) + '@0'
                                cur_bus.running = True
                                cur_bus.time_count = int((self.line.dist_list[int(loc_1) - 1] - 50) / self.line.speed_list[
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
                            for cab in cur_bus.cab_id:
                                self.all_cabs[cab]['end_t'] = self.t
                        else:
                            cur_bus.loc, cur_bus.run_next = loc_1 + '@5', str(int(loc_1) + 1) + '@0'
                            cur_bus.running = True
                            cur_bus.time_count = int((self.line.dist_list[int(loc_1) - 1] - 50) / self.line.speed_list[
                                int(loc_1) - 1])
                            for cab in cur_bus.cab_id:
                                self.all_cabs[cab]['dist'] += self.line.dist_list[int(loc_1) - 1]  # 记录累计距离
                            # record number of passengers
                            for k in range(len(cur_bus.cab_id)):
                                self.all_cabs[cur_bus.cab_id[k]]['dep_time'].append(self.t)
                                self.all_cabs[cur_bus.cab_id[k]]['pas_num'].append(len(cur_bus.pass_list[k]))

    def get_dec_order(self):
        """决策顺序生成"""
        available_bus = [b.bus_id for b in self.all_buses.values() if b.state != 'end']
        return sorted(available_bus, key=lambda x: self.all_buses[x].loc_num, reverse=True)

    def is_bus_finished(self):
        return len([b for b in self.all_buses.values() if b.state != 'end']) < 0.8

    def update_dep(self, dec: int, cap: int):
        """更新最新的发车决策"""
        self.dep_decider.last_dep = self.t
        # ------------ create new bus ----------------
        cur_bus_id, cur_cab_id = self.next_bus_id, self.next_cab_id
        self.all_buses[cur_bus_id] = Bus(
            cab_num=dec, max_num_list=[cap for _ in range(dec)],
            cab_id=list(range(cur_cab_id, cur_cab_id + dec)), bus_id=cur_bus_id)
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

    def apply_action_in_assign(self, bus_id, bus_dec):
        """执行 assign_action 中进行的决策"""
        if bus_dec['stop']:
            self.all_buses[bus_id].to_stop = True
            self.all_buses[bus_id].stop_count += self.stop_time
        # todo

    def get_statistics(self):
        """获取系统表现统计数据"""
        # 乘客统计数据
        avg_travel_t, avg_wait_t, full_t, avg_station_wait_t = 0, 0, 0, 0
        for pas in self.all_passengers.values():
            pas.get_statistics(loc_list=self.line.loc_list)
            avg_travel_t += pas.travel_t
            avg_wait_t += pas.bus_wait_t
            full_t += pas.full_jour_t
            avg_station_wait_t += pas.station_wait_t
        avg_travel_t /= len(self.all_passengers)
        avg_wait_t /= len(self.all_passengers)
        full_t /= len(self.all_passengers)
        avg_station_wait_t /= len(self.all_passengers)

        # 车辆出行数据
        if self.sim_mode == 'baseline':
            # 能耗
            power_consump_speed = sum([dist['dist'] for dist in self.all_cabs.values()]) * CONSUMP_SPEED_OLD
            power_consump_cond = sum([dist['dist'] for dist in self.all_cabs.values()]) * CONSUMP_CONDITION_OLD
            # 乘客数量
            avg_pas_num_list = [sum(cab['pas_num'])/len(cab['pas_num']) for cab in self.all_cabs.values()]
            avg_pas_num = np.mean(avg_pas_num_list)
            pas_num_list = [cab['pas_num'] for cab in self.all_cabs.values()]
            max_pas_num = np.max(pas_num_list)
            avg_pas_num_list_early = [sum(cab['pas_num']) / len(cab['pas_num']) for cab in self.all_cabs.values()
                                      if 6 * 3600 <= cab['dep_time'][0] < 8 * 3600]
            avg_pas_num_early = np.mean(avg_pas_num_list_early)
            avg_pas_num_list_noon = [sum(cab['pas_num']) / len(cab['pas_num']) for cab in self.all_cabs.values()
                                      if 10 * 3600 <= cab['dep_time'][0] < 12 * 3600]
            avg_pas_num_noon = np.mean(avg_pas_num_list_noon)
            avg_pas_num_list_late = [sum(cab['pas_num']) / len(cab['pas_num']) for cab in self.all_cabs.values()
                                      if 16 * 3600 <= cab['dep_time'][0] < 18 * 3600]
            avg_pas_num_late = np.mean(avg_pas_num_list_late)

        return {
            'avg_travel_t(on bus, s)': avg_travel_t,
            'avg_travel_t(full, s)': full_t,
            'avg_wait_t(s)': avg_wait_t,
            'avg_station_wait_t(s)': avg_station_wait_t,
            'power consumption(equal speed, kWh)': power_consump_speed,
            'power consumption(condition, kWh)': power_consump_cond,
            'driver wage(RMB, year)': 20 * DRIVER_WAGE_OLD,  # avg_travel_time / departure_duration = 20
            'max_pas_num': max_pas_num,
            'avg_pas_num(all day)': avg_pas_num,
            'avg_pas_num(early)': avg_pas_num_early,
            'avg_pas_num(noon)': avg_pas_num_noon,
            'avg_pas_num(late)': avg_pas_num_late,
            'carbon emission(g)': 0.31 * 0.23 * power_consump_cond
        }


if __name__ == '__main__':

    line_info = read_in()

    sim = Sim(**line_info, sim_mode='baseline')
    sim.run()
    sim_result = sim.get_statistics()
