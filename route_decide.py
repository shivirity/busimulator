import logging

from env.bus import Bus
from env.line import Line
from env.passenger import Passenger

from consts import RATE_MAX_STOP, MAX_SEP_STATIONS


class route_decider:

    def __init__(self, sim_mode: str = 'single'):
        """路线决策器"""
        assert sim_mode in ['baseline', 'single', 'multi']
        self.mode = sim_mode

    def decide_stop_action_baseline(self, cur_bus: Bus, line: Line):
        """
        决策车辆在当前站的上下客以及下一站的车辆决策（单一车辆决策，用于baseline）

        :param cur_bus: 当前车辆
        :param line: 当前主线
        :return: 动作字典(key in ['stop'])
        """
        assert self.mode == 'baseline'
        cur_station = int(cur_bus.loc.split('@')[0])
        if cur_bus.is_to_stop(station=cur_station) or len(line.main_line[cur_station]) > 0:
            # 有乘客需要下车或有乘客需要上车
            return {'stop': True, }
        else:
            return {'stop': False, }

    def decide_stop_action_single(self, bus_group: list, bus_info: dict, line: Line):
        """
        决策一组车辆在当前站的停站决策，用于单线优化

        :param bus_group: 待决策的车辆列表
        :param bus_info: 所有bus信息，self.all_buses
        :param line: 仿真主线
        :return: 动作字典(key in ['stop', 'comb', 'sep'])
        """
        assert self.mode == 'single'
        # divide bus_group into waiting and not waiting
        waiting_list = [bus for bus in bus_group if bus_info[bus].is_waiting is True]
        not_waiting_list = [bus for bus in bus_group if bus_info[bus].is_waiting is False]
        dec_dict = {}
        stop_list, alter_stop_list, cur_loc, cur_station = \
            [], [], bus_info[bus_group[0]].loc, int(bus_info[bus_group[0]].loc.split('@')[0])
        for bus in not_waiting_list:
            cur_bus = bus_info[bus]
            assert cur_bus.able is True
            if self.time2dec(loc=cur_loc, state=cur_bus.is_waiting):
                if cur_bus.is_to_stop(station=cur_station):
                    dec_dict[bus] = True
                    stop_list.append(bus)
                else:
                    if len(waiting_list) > 0.8:
                        dec_dict[bus] = False
                        logging.warning(f'{bus} meets waiting {waiting_list} at station {cur_station}')
                    else:
                        if len(line.main_line[cur_station]) < 0.8:
                            dec_dict[bus] = False
                        else:
                            alter_stop_list.append(bus)
        if len(alter_stop_list) > 0:
            if len(stop_list) > 0:
                max_num = sum([bus_info[bus].max_num for bus in stop_list])
                pas_num = sum([bus_info[bus].pass_num for bus in stop_list])
                stop_pas_num = sum([bus_info[bus].stop_pass_num(station=cur_station) for bus in stop_list])
                up_num = len(line.main_line[cur_station])
                est_num = pas_num - stop_pas_num + up_num
                if est_num < max_num * RATE_MAX_STOP:
                    # enough
                    for bus in alter_stop_list:
                        dec_dict[bus] = False
                else:
                    logging.warning(f'seats are not enough at station {cur_station} '
                                    f'with alter_stop: {alter_stop_list} and stop: {stop_list}')
                    alter_stop_order = \
                        sorted(
                            alter_stop_list,
                            key=lambda x: bus_info[x].sum_stations_to_go(station=cur_station), reverse=False
                        )
                    res_num = up_num - (max_num * RATE_MAX_STOP - pas_num + stop_pas_num)
                    enough_flag = False
                    for alter_bus in alter_stop_order:
                        if bus_info[alter_bus].max_num == bus_info[alter_bus].pass_num:
                            dec_dict[alter_bus] = False
                        else:
                            alter_num = bus_info[alter_bus].max_num - bus_info[alter_bus].pass_num
                            if not enough_flag:
                                dec_dict[alter_bus] = True
                                res_num -= alter_num
                                if res_num <= 0:
                                    enough_flag = True
                            else:
                                dec_dict[alter_bus] = False
            else:
                res_num = len(line.main_line[cur_station])
                alter_stop_order = \
                    sorted(
                        alter_stop_list,
                        key=lambda x: bus_info[x].sum_stations_to_go(station=cur_station), reverse=False
                    )
                enough_flag = False
                for alter_bus in alter_stop_order:
                    if bus_info[alter_bus].max_num == bus_info[alter_bus].pass_num:
                        dec_dict[alter_bus] = False
                    else:
                        alter_num = bus_info[alter_bus].max_num - bus_info[alter_bus].pass_num
                        if not enough_flag:
                            dec_dict[alter_bus] = True
                            res_num -= alter_num
                            if res_num <= 0:
                                enough_flag = True
                        else:
                            dec_dict[alter_bus] = False
        else:
            pass

        return dec_dict

    @staticmethod
    def time2dec(loc: str, state: bool):
        """
        是否到达决策时间点（决策在进站前进行，静态决策）

        :param loc: 车辆（bus）位置
        :param state: 车辆状态，是否停站等待中
        :return:
        """
        return (not state) and loc.split('@')[1] == '0'
