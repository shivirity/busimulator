import logging
import random
from env.bus import Bus
from env.line import Line

from consts import RATE_MAX_STOP, MAIN_LINE_STOP_TURN_THRESHOLD, MAIN_LINE_STOP_TURN_RATE_THRESHOLD, \
    ONLY_MAIN_LINE_STOP_THRESHOLD, MAIN_LINE_TURN_MAX_PASS_NUM

random.seed(42)


class RouteDecider:

    def __init__(self, sim_mode: str = 'single'):
        """路线决策器"""
        assert sim_mode in ['baseline', 'single', 'multi', 'multi_order']
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
        :return: 动作字典(key in ['stop'])
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
                        # logging.warning(f'{bus} meets waiting {waiting_list} at station {cur_station}')
                    else:
                        if len(line.main_line[cur_station]) < 0.8:
                            dec_dict[bus] = False
                        else:
                            alter_stop_list.append(bus)
        if len(alter_stop_list) > 0:  # 停留池
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
                    # logging.warning(f'seats are not enough at station {cur_station} '
                    #                 f'with alter_stop: {alter_stop_list} and stop: {stop_list}')
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

    def decide_stop_action_multi(self, loc: str, bus_group: list, bus_info: dict, line: Line, rule: str):
        """
        决策一组车辆在当前站的停站决策，用于主线+支线优化

        :param loc: 当前站点位置
        :param bus_group: 待决策的车辆列表
        :param bus_info: 所有bus信息，self.all_buses
        :param line: 仿真线路信息
        :param rule: 决策逻辑, in ['down_first', 'up_first']
        :return: 动作字典(key in ['stop', 'turn', 'return_stop'])
        """
        assert self.mode in ['multi', 'multi_order']
        main_id, side_id, run_state = map(int, loc.split('#'))
        dec_dict = {}
        if rule == 'down_first':
            if side_id > 0.2:  # side line
                dec_stop_list = []
                for bus in bus_group:
                    cur_bus, cur_loc = bus_info[bus], bus_info[bus].loc
                    main_id, side_id, side_order, run_state = map(int, cur_loc.split('#'))
                    if cur_bus.is_returning:  # returning
                        if cur_bus.is_waiting is False:
                            waiting_group = [bus for bus in bus_group if bus_info[bus].is_waiting is True]
                            if len(waiting_group) == 0 and len(dec_stop_list) == 0 and \
                                    line.side_line[f'{main_id}#{side_id}'].side_stations[side_order]['pool']:
                                if cur_bus.pass_num < cur_bus.max_num:
                                    dec_dict[bus] = {'stop': True, 'turn': 0}
                                    dec_stop_list.append(cur_bus.bus_id)
                                else:
                                    dec_dict[bus] = {'stop': False, 'turn': 0}
                            else:
                                dec_dict[bus] = {'stop': False, 'turn': 0}
                    else:  # not returning
                        if cur_bus.is_waiting is False:
                            if side_order < len(line.side_line[f'{main_id}#{side_id}'].side_stations):
                                if cur_bus.stop_pass_num(station=f'{main_id}#{side_id}#{side_order}') > 0:  # 有人下车
                                    dec_dict[cur_bus.bus_id] = {'stop': True, 'turn': 0}
                                else:
                                    dec_dict[cur_bus.bus_id] = {'stop': False, 'turn': 0}
                            else:
                                if cur_bus.stop_pass_num(station=f'{main_id}#{side_id}#{side_order}') > 0 or \
                                        line.side_line[f'{main_id}#{side_id}'].side_stations[side_order]['pool']:
                                    if cur_bus.stop_pass_num(station=f'{main_id}#{side_id}#{side_order}') == 0 and \
                                            cur_bus.pass_num == cur_bus.max_num:
                                        dec_dict[cur_bus.bus_id] = {'stop': False, 'turn': 0}
                                    else:
                                        dec_dict[cur_bus.bus_id] = {'stop': True, 'turn': 0}
                                else:
                                    dec_dict[cur_bus.bus_id] = {'stop': False, 'turn': 0}

            else:  # main line
                dec_num = 0
                cur_loc = bus_info[bus_group[0]].loc
                main_id, side_id, side_order, run_state = map(int, cur_loc.split('#'))
                # returned buses
                return_run_buses = [bus for bus in bus_group if
                                    (bus_info[bus].is_returning is True and bus_info[bus].is_waiting is False)]
                # main_line stop buses
                stop_buses = [bus for bus in bus_group if bus_info[bus].is_waiting is True]
                # new arrive buses, may turn to different sides
                dis_return_run_buses = [bus for bus in bus_group if
                                        (bus_info[bus].is_returning is False and bus_info[bus].is_waiting is False)]

                # return stop
                if len(return_run_buses) > 0:
                    cannot_stop_buses = [bus for bus in return_run_buses if bus_info[bus].can_return_stop is False]
                    for bus in cannot_stop_buses:
                        dec_dict[bus] = {'stop': False, 'turn': 0}
                        dec_num += 1
                    # 多车辆停留问题
                    can_stop_buses = [bus for bus in return_run_buses if bus_info[bus].can_return_stop is True]
                    if len(can_stop_buses) > 0:  # 停留池
                        if len(stop_buses) > 0:
                            max_num = sum([bus_info[bus].max_num for bus in stop_buses])
                            pas_num = sum([bus_info[bus].pass_num for bus in stop_buses])
                            stop_pas_num = sum([bus_info[bus].stop_pass_num(station=main_id) for bus in stop_buses])
                            up_num = len(line.main_line[main_id])
                            est_num = pas_num - stop_pas_num + up_num
                            if est_num < max_num * RATE_MAX_STOP:
                                # enough
                                for bus in can_stop_buses:
                                    dec_dict[bus] = {'stop': False, 'turn': 0}
                                    dec_num += 1
                            else:
                                logging.warning(f'seats are not enough at station {main_id} '
                                                f'with alter_stop: {can_stop_buses} and stop: {stop_buses}')
                                alter_stop_order = \
                                    sorted(
                                        can_stop_buses,
                                        key=lambda x: bus_info[x].sum_stations_to_go(station=main_id), reverse=False
                                    )
                                res_num = up_num - (max_num * RATE_MAX_STOP - pas_num + stop_pas_num)
                                enough_flag = False
                                for alter_bus in alter_stop_order:
                                    if bus_info[alter_bus].max_num == bus_info[alter_bus].pass_num:
                                        dec_dict[alter_bus] = {'stop': False, 'turn': 0}
                                        dec_num += 1
                                    else:
                                        alter_num = bus_info[alter_bus].max_num - bus_info[alter_bus].pass_num
                                        if not enough_flag:
                                            dec_dict[alter_bus] = {'stop': True, 'turn': 0}
                                            dec_num += 1
                                            res_num -= alter_num
                                            if res_num <= 0:
                                                enough_flag = True
                                        else:
                                            dec_dict[alter_bus] = {'stop': False, 'turn': 0}
                                            dec_num += 1
                        else:
                            res_num = len(line.main_line[main_id])
                            alter_stop_order = \
                                sorted(
                                    can_stop_buses,
                                    key=lambda x: bus_info[x].sum_stations_to_go(station=main_id), reverse=False
                                )
                            enough_flag = False
                            for alter_bus in alter_stop_order:
                                if bus_info[alter_bus].max_num == bus_info[alter_bus].pass_num:
                                    dec_dict[alter_bus] = {'stop': False, 'turn': 0}
                                    dec_num += 1
                                else:
                                    alter_num = bus_info[alter_bus].max_num - bus_info[alter_bus].pass_num
                                    if not enough_flag:
                                        dec_dict[alter_bus] = {'stop': True, 'turn': 0}
                                        dec_num += 1
                                        res_num -= alter_num
                                        if res_num <= 0:
                                            enough_flag = True
                                    else:
                                        dec_dict[alter_bus] = {'stop': False, 'turn': 0}
                                        dec_num += 1
                    else:
                        pass

                # not return stop
                if len(dis_return_run_buses) > 0:
                    decide_turn = {1: [bus for bus in bus_group if bus_info[bus].to_turn == 1],  # 正在等待的车中确定转向的
                                   2: [bus for bus in bus_group if bus_info[bus].to_turn == 2]}
                    # assert len(decide_turn[1]) <= 1 and len(decide_turn[2]) <= 1
                    # 在原地下车的人
                    have_down_list = [bus for bus in dis_return_run_buses if bus_info[bus].is_to_stop(station=main_id)]
                    # 没有原地下车的人
                    no_down_list = [val for val in dis_return_run_buses if val not in have_down_list]
                    # 分配原地不下车
                    if len(no_down_list) > 0:
                        for bus in no_down_list:
                            cur_bus = bus_info[bus]
                            side_1_down, side_2_down = cur_bus.stop_num_at_side_line(main_line_id=main_id)
                            if side_1_down > 0.2 and side_2_down < 0.2:  # #1
                                dec_dict[bus] = {'stop': False, 'turn': 1, 'can_return_stop': True}
                                decide_turn[1].append(bus)
                                dec_num += 1
                            elif side_1_down < 0.2 and side_2_down > 0.2:  # #2
                                dec_dict[bus] = {'stop': False, 'turn': 2, 'can_return_stop': True}
                                decide_turn[2].append(bus)
                                dec_num += 1
                            elif side_1_down > 0.2 and side_2_down > 0.2:  # #1#2, 另一条路的人需要在主线下车
                                if side_1_down != side_2_down:
                                    turn_direc = 1 if side_1_down > side_2_down else 2
                                else:
                                    turn_direc = 1 if sum([len(station['pool'])
                                                           for station in
                                                           line.side_line[f'{main_id}#1'].side_stations.values()]) >= \
                                                      sum([len(station['pool'])
                                                           for station in
                                                           line.side_line[
                                                               f'{main_id}#2'].side_stations.values()]) else 2
                                dec_dict[bus] = {'stop': True, 'turn': turn_direc, 'can_return_stop': False}
                                decide_turn[turn_direc].append(bus)
                                dec_num += 1
                            else:
                                side_1_bus_num = [bus.bus_id for bus in bus_info.values()
                                                  if bus.able is True and bus.loc.startswith(f'{main_id}#1')]
                                side_2_bus_num = [bus.bus_id for bus in bus_info.values()
                                                  if bus.able is True and bus.loc.startswith(f'{main_id}#2')]
                                if len(side_1_bus_num) + len(decide_turn[1]) > 0.2 and \
                                        len(side_2_bus_num) + len(decide_turn[2]) > 0.2:
                                    # 两边都有车，且两边都没有下车
                                    if len(line.main_line[main_id]) > 0 and len(
                                            stop_buses) <= ONLY_MAIN_LINE_STOP_THRESHOLD and cur_bus.pass_num < cur_bus.max_num:  # 有人在主线上
                                        dec_dict[bus] = {'stop': True, 'turn': 0, 'can_return_stop': False}
                                    else:
                                        dec_dict[bus] = {'stop': False, 'turn': 0, 'can_return_stop': False}
                                    dec_num += 1
                                elif len(side_1_bus_num) + len(decide_turn[1]) > 0.2:  # 有车在#1
                                    if sum([len(station['pool'])
                                            for station in
                                            line.side_line[f'{main_id}#2'].side_stations.values()]) > 0.2:
                                        # 有人在#2等待
                                        dec_dict[bus] = {'stop': False, 'turn': 2, 'can_return_stop': True}
                                        decide_turn[2].append(bus)
                                        dec_num += 1
                                    else:
                                        if len(line.main_line[main_id]) > 0 and len(
                                                stop_buses) <= ONLY_MAIN_LINE_STOP_THRESHOLD and cur_bus.pass_num < cur_bus.max_num:  # 有人在主线上
                                            dec_dict[bus] = {'stop': True, 'turn': 0, 'can_return_stop': False}
                                        else:
                                            dec_dict[bus] = {'stop': False, 'turn': 0, 'can_return_stop': False}
                                        dec_num += 1
                                elif len(side_2_bus_num) + len(decide_turn[2]) > 0.2:  # 有车在#2
                                    if sum([len(station['pool'])
                                            for station in
                                            line.side_line[f'{main_id}#1'].side_stations.values()]) > 0.2:
                                        # 有人在#1等待
                                        dec_dict[bus] = {'stop': False, 'turn': 1, 'can_return_stop': True}
                                        decide_turn[1].append(bus)
                                        dec_num += 1
                                    else:
                                        if len(line.main_line[main_id]) > 0 and len(
                                                stop_buses) <= ONLY_MAIN_LINE_STOP_THRESHOLD and cur_bus.pass_num < cur_bus.max_num:  # 有人在主线上
                                            dec_dict[bus] = {'stop': True, 'turn': 0, 'can_return_stop': False}
                                        else:
                                            dec_dict[bus] = {'stop': False, 'turn': 0, 'can_return_stop': False}
                                        dec_num += 1
                                else:
                                    sum_1_up = sum([len(station['pool'])
                                                    for station in
                                                    line.side_line[f'{main_id}#1'].side_stations.values()])
                                    sum_2_up = sum([len(station['pool'])
                                                    for station in
                                                    line.side_line[f'{main_id}#2'].side_stations.values()])
                                    if sum_1_up > 0.2 or sum_2_up > 0.2:
                                        turn_direc = 1 if sum_1_up >= sum_2_up else 2
                                        dec_dict[bus] = {'stop': False, 'turn': turn_direc, 'can_return_stop': True}
                                        decide_turn[turn_direc].append(bus)
                                        dec_num += 1
                                    else:
                                        if len(line.main_line[main_id]) > 0 and len(
                                                stop_buses) <= ONLY_MAIN_LINE_STOP_THRESHOLD and cur_bus.pass_num < cur_bus.max_num:  # 有人在主线上
                                            dec_dict[bus] = {'stop': True, 'turn': 0, 'can_return_stop': False}
                                        else:
                                            dec_dict[bus] = {'stop': False, 'turn': 0, 'can_return_stop': False}
                                        dec_num += 1
                    # 分配原地下车
                    if len(have_down_list) > 0:
                        for bus in have_down_list:
                            cur_bus = bus_info[bus]
                            side_1_down, side_2_down = cur_bus.stop_num_at_side_line(main_line_id=main_id)

                            if side_1_down > 0.2 and side_2_down < 0.2:  # #1上有人下车
                                if side_1_down >= MAIN_LINE_STOP_TURN_THRESHOLD and \
                                        side_1_down / cur_bus.pass_num >= MAIN_LINE_STOP_TURN_RATE_THRESHOLD:
                                    dec_dict[bus] = {'stop': True, 'turn': 1, 'can_return_stop': False}
                                    decide_turn[1].append(bus)
                                    dec_num += 1
                                else:
                                    dec_dict[bus] = {'stop': True, 'turn': 0, 'can_return_stop': False}
                                    dec_num += 1
                            elif side_1_down < 0.2 and side_2_down > 0.2:  # #2上有人下车
                                if side_2_down >= MAIN_LINE_STOP_TURN_THRESHOLD and \
                                        side_2_down / cur_bus.pass_num >= MAIN_LINE_STOP_TURN_RATE_THRESHOLD:
                                    dec_dict[bus] = {'stop': True, 'turn': 2, 'can_return_stop': False}
                                    decide_turn[2].append(bus)
                                    dec_num += 1
                                else:
                                    dec_dict[bus] = {'stop': True, 'turn': 0, 'can_return_stop': False}
                                    dec_num += 1
                            elif side_1_down > 0.2 and side_2_down > 0.2:  # #1#2上都有人下车
                                if max(side_1_down, side_2_down) >= MAIN_LINE_STOP_TURN_THRESHOLD and \
                                        max(side_1_down,
                                            side_2_down) / cur_bus.pass_num >= MAIN_LINE_STOP_TURN_RATE_THRESHOLD:
                                    turn_direc = 1 if side_1_down >= side_2_down else 2
                                    dec_dict[bus] = {'stop': True, 'turn': turn_direc, 'can_return_stop': False}
                                    decide_turn[turn_direc].append(bus)
                                    dec_num += 1
                                else:
                                    dec_dict[bus] = {'stop': True, 'turn': 0, 'can_return_stop': False}
                                    dec_num += 1
                            else:  # 支线没有人下车
                                side_1_bus_num = [bus.bus_id for bus in bus_info.values()
                                                  if bus.able is True and bus.loc.startswith(f'{main_id}#1')]
                                side_2_bus_num = [bus.bus_id for bus in bus_info.values()
                                                  if bus.able is True and bus.loc.startswith(f'{main_id}#2')]
                                if len(side_1_bus_num) + len(decide_turn[1]) > 0.2 and \
                                        len(side_2_bus_num) + len(decide_turn[2]) > 0.2:
                                    # 两边都有车，但是都不能下车
                                    dec_dict[bus] = {'stop': True, 'turn': 0, 'can_return_stop': False}
                                    dec_num += 1
                                elif len(side_1_bus_num) + len(decide_turn[1]) > 0.2:
                                    if sum([len(station['pool'])
                                            for station in
                                            line.side_line[f'{main_id}#2'].side_stations.values()]) > 0.2:
                                        # 有人在#2等待
                                        dec_dict[bus] = {'stop': True, 'turn': 2, 'can_return_stop': False}
                                        decide_turn[2].append(bus)
                                        dec_num += 1
                                    else:
                                        dec_dict[bus] = {'stop': True, 'turn': 0, 'can_return_stop': False}
                                        dec_num += 1
                                elif len(side_2_bus_num) + len(decide_turn[2]) > 0.2:
                                    if sum([len(station['pool'])
                                            for station in
                                            line.side_line[f'{main_id}#1'].side_stations.values()]) > 0.2:
                                        # 有人在#1等待
                                        dec_dict[bus] = {'stop': True, 'turn': 1, 'can_return_stop': False}
                                        decide_turn[1].append(bus)
                                        dec_num += 1
                                    else:
                                        dec_dict[bus] = {'stop': True, 'turn': 0, 'can_return_stop': False}
                                        dec_num += 1
                                else:
                                    sum_1_up = sum([len(station['pool'])
                                                    for station in
                                                    line.side_line[f'{main_id}#1'].side_stations.values()])
                                    sum_2_up = sum([len(station['pool'])
                                                    for station in
                                                    line.side_line[f'{main_id}#2'].side_stations.values()])
                                    if sum_1_up > 0.2 or sum_2_up > 0.2:

                                        if sum_1_up != sum_2_up:
                                            turn_direc = 1 if sum_1_up > sum_2_up else 2
                                        else:
                                            turn_direc = random.randint(1, 2)
                                        dec_dict[bus] = {'stop': True, 'turn': turn_direc, 'can_return_stop': False}
                                        decide_turn[turn_direc].append(bus)
                                        dec_num += 1
                                    else:
                                        dec_dict[bus] = {'stop': True, 'turn': 0, 'can_return_stop': False}
                                        dec_num += 1

                assert dec_num + len(stop_buses) == len(
                    bus_group), f'{loc}, {dec_num}, {len(bus_group)}, {len(stop_buses)}'

        elif rule == 'up_first':
            if side_id > 0.2:  # side line
                dec_stop_list = []
                for bus in bus_group:
                    cur_bus, cur_loc = bus_info[bus], bus_info[bus].loc
                    main_id, side_id, side_order, run_state = map(int, cur_loc.split('#'))
                    if cur_bus.is_returning:  # returning
                        if cur_bus.is_waiting is False:
                            waiting_group = [bus for bus in bus_group if bus_info[bus].is_waiting is True]
                            if len(waiting_group) == 0 and len(dec_stop_list) == 0 and \
                                    line.side_line[f'{main_id}#{side_id}'].side_stations[side_order]['pool']:
                                if cur_bus.pass_num < cur_bus.max_num:
                                    dec_dict[bus] = {'stop': True, 'turn': 0}
                                    dec_stop_list.append(cur_bus.bus_id)
                                else:
                                    dec_dict[bus] = {'stop': False, 'turn': 0}
                            else:
                                dec_dict[bus] = {'stop': False, 'turn': 0}

                    else:  # not returning
                        if cur_bus.is_waiting is False:
                            if side_order < len(line.side_line[f'{main_id}#{side_id}'].side_stations):
                                if cur_bus.stop_pass_num(station=f'{main_id}#{side_id}#{side_order}') > 0:  # 有人下车
                                    dec_dict[cur_bus.bus_id] = {'stop': True, 'turn': 0}
                                else:
                                    dec_dict[cur_bus.bus_id] = {'stop': False, 'turn': 0}
                            else:
                                if cur_bus.stop_pass_num(station=f'{main_id}#{side_id}#{side_order}') > 0 or \
                                        line.side_line[f'{main_id}#{side_id}'].side_stations[side_order]['pool']:
                                    if cur_bus.stop_pass_num(station=f'{main_id}#{side_id}#{side_order}') == 0 and \
                                            cur_bus.pass_num == cur_bus.max_num:
                                        dec_dict[cur_bus.bus_id] = {'stop': False, 'turn': 0}
                                    else:
                                        dec_dict[cur_bus.bus_id] = {'stop': True, 'turn': 0}
                                else:
                                    dec_dict[cur_bus.bus_id] = {'stop': False, 'turn': 0}

            else:  # main line
                dec_num = 0
                cur_loc = bus_info[bus_group[0]].loc
                main_id, side_id, side_order, run_state = map(int, cur_loc.split('#'))
                # returned buses
                return_run_buses = [bus for bus in bus_group if
                                    (bus_info[bus].is_returning is True and bus_info[bus].is_waiting is False)]
                # main_line stop buses
                stop_buses = [bus for bus in bus_group if bus_info[bus].is_waiting is True]
                # new arrive buses, may turn to different sides
                dis_return_run_buses = [bus for bus in bus_group if
                                        (bus_info[bus].is_returning is False and bus_info[bus].is_waiting is False)]

                # return stop
                if len(return_run_buses) > 0:
                    cannot_stop_buses = [bus for bus in return_run_buses if bus_info[bus].can_return_stop is False]
                    for bus in cannot_stop_buses:
                        dec_dict[bus] = {'stop': False, 'turn': 0}
                        dec_num += 1
                    # 多车辆停留问题
                    can_stop_buses = [bus for bus in return_run_buses if bus_info[bus].can_return_stop is True]
                    if len(can_stop_buses) > 0:  # 停留池
                        if len(stop_buses) > 0:
                            max_num = sum([bus_info[bus].max_num for bus in stop_buses])
                            pas_num = sum([bus_info[bus].pass_num for bus in stop_buses])
                            stop_pas_num = sum([bus_info[bus].stop_pass_num(station=main_id) for bus in stop_buses])
                            up_num = len(line.main_line[main_id])
                            est_num = pas_num - stop_pas_num + up_num
                            if est_num < max_num * RATE_MAX_STOP:
                                # enough
                                for bus in can_stop_buses:
                                    dec_dict[bus] = {'stop': False, 'turn': 0}
                                    dec_num += 1
                            else:
                                logging.warning(f'seats are not enough at station {main_id} '
                                                f'with alter_stop: {can_stop_buses} and stop: {stop_buses}')
                                alter_stop_order = \
                                    sorted(
                                        can_stop_buses,
                                        key=lambda x: bus_info[x].sum_stations_to_go(station=main_id), reverse=False
                                    )
                                res_num = up_num - (max_num * RATE_MAX_STOP - pas_num + stop_pas_num)
                                enough_flag = False
                                for alter_bus in alter_stop_order:
                                    if bus_info[alter_bus].max_num == bus_info[alter_bus].pass_num:
                                        dec_dict[alter_bus] = {'stop': False, 'turn': 0}
                                        dec_num += 1
                                    else:
                                        alter_num = bus_info[alter_bus].max_num - bus_info[alter_bus].pass_num
                                        if not enough_flag:
                                            dec_dict[alter_bus] = {'stop': True, 'turn': 0}
                                            dec_num += 1
                                            res_num -= alter_num
                                            if res_num <= 0:
                                                enough_flag = True
                                        else:
                                            dec_dict[alter_bus] = {'stop': False, 'turn': 0}
                                            dec_num += 1
                        else:
                            res_num = len(line.main_line[main_id])
                            alter_stop_order = \
                                sorted(
                                    can_stop_buses,
                                    key=lambda x: bus_info[x].sum_stations_to_go(station=main_id), reverse=False
                                )
                            enough_flag = False
                            for alter_bus in alter_stop_order:
                                if bus_info[alter_bus].max_num == bus_info[alter_bus].pass_num:
                                    dec_dict[alter_bus] = {'stop': False, 'turn': 0}
                                    dec_num += 1
                                else:
                                    alter_num = bus_info[alter_bus].max_num - bus_info[alter_bus].pass_num
                                    if not enough_flag:
                                        dec_dict[alter_bus] = {'stop': True, 'turn': 0}
                                        dec_num += 1
                                        res_num -= alter_num
                                        if res_num <= 0:
                                            enough_flag = True
                                    else:
                                        dec_dict[alter_bus] = {'stop': False, 'turn': 0}
                                        dec_num += 1
                    else:
                        pass

                # not return stop
                if len(dis_return_run_buses) > 0:
                    decide_turn = {1: [bus for bus in bus_group if bus_info[bus].to_turn == 1],  # 正在等待的车中确定转向的
                                   2: [bus for bus in bus_group if bus_info[bus].to_turn == 2]}
                    # 在原地下车的人
                    have_down_list = [bus for bus in dis_return_run_buses if bus_info[bus].is_to_stop(station=main_id)]
                    # 没有原地下车的人
                    no_down_list = [val for val in dis_return_run_buses if val not in have_down_list]
                    # 已决策在主线停留的车辆
                    main_stop_list = []

                    # no_down_list中根据剩余行程排序
                    no_down_list = \
                        sorted(
                            no_down_list,
                            key=lambda x: bus_info[x].sum_stations_to_go(station=main_id), reverse=False
                        )

                    # 分配原地不下车
                    if len(no_down_list) > 0:
                        for bus in no_down_list:
                            cur_bus = bus_info[bus]
                            sum_1_up = sum([len(station['pool'])
                                            for station in
                                            line.side_line[f'{main_id}#1'].side_stations.values()])
                            sum_2_up = sum([len(station['pool'])
                                            for station in
                                            line.side_line[f'{main_id}#2'].side_stations.values()])
                            side_1_bus_num = len([bus.bus_id for bus in bus_info.values()
                                                  if bus.able is True and bus.loc.startswith(f'{main_id}#1')])
                            side_2_bus_num = len([bus.bus_id for bus in bus_info.values()
                                                  if bus.able is True and bus.loc.startswith(f'{main_id}#2')])
                            side_1_down, side_2_down = cur_bus.stop_num_at_side_line(main_line_id=main_id)
                            if side_1_bus_num + len(decide_turn[1]) > 0.2 and side_2_bus_num + len(
                                    decide_turn[2]) > 0.2:
                                # 两边都有车且都没有原地下车
                                if len(line.main_line[main_id]) > 0 and \
                                        len(stop_buses) + len(have_down_list) + len(main_stop_list) <= ONLY_MAIN_LINE_STOP_THRESHOLD and \
                                        cur_bus.pass_num < cur_bus.max_num:  # 有人在主线上
                                    dec_dict[bus] = {'stop': True, 'turn': 0, 'can_return_stop': False}
                                    main_stop_list.append(bus)
                                else:
                                    if side_1_down + side_2_down > 0.2:
                                        dec_dict[bus] = {'stop': True, 'turn': 0, 'can_return_stop': False}
                                        main_stop_list.append(bus)
                                    else:
                                        dec_dict[bus] = {'stop': False, 'turn': 0, 'can_return_stop': False}
                                dec_num += 1
                            elif side_1_bus_num + len(decide_turn[1]) > 0.2:  # 有车在#1
                                if sum_2_up > 0.2:
                                    # 有人在#2等待
                                    if cur_bus.pass_num <= MAIN_LINE_TURN_MAX_PASS_NUM:
                                        if side_1_down > 0:
                                            dec_dict[bus] = {'stop': True, 'turn': 2, 'can_return_stop': True}
                                            main_stop_list.append(bus)
                                        else:
                                            dec_dict[bus] = {'stop': False, 'turn': 2, 'can_return_stop': True}
                                        decide_turn[2].append(bus)
                                    else:
                                        if side_1_down + side_2_down > 0:
                                            dec_dict[bus] = {'stop': True, 'turn': 0, 'can_return_stop': False}
                                            main_stop_list.append(bus)
                                        else:
                                            dec_dict[bus] = {'stop': False, 'turn': 0, 'can_return_stop': False}
                                    dec_num += 1
                                else:
                                    if len(line.main_line[main_id]) > 0 and \
                                            len(stop_buses) + len(have_down_list) + len(main_stop_list) <= ONLY_MAIN_LINE_STOP_THRESHOLD and \
                                            cur_bus.pass_num < cur_bus.max_num:
                                        dec_dict[bus] = {'stop': True, 'turn': 0, 'can_return_stop': False}
                                        main_stop_list.append(bus)
                                    else:
                                        if side_1_down + side_2_down > 0.2:
                                            dec_dict[bus] = {'stop': True, 'turn': 0, 'can_return_stop': False}
                                            main_stop_list.append(bus)
                                        else:
                                            dec_dict[bus] = {'stop': False, 'turn': 0, 'can_return_stop': False}
                                    dec_num += 1
                            elif side_2_bus_num + len(decide_turn[2]) > 0.2:
                                if sum_1_up > 0.2:
                                    # 有人在#1等待
                                    if cur_bus.pass_num <= MAIN_LINE_TURN_MAX_PASS_NUM:
                                        if side_2_down > 0:
                                            dec_dict[bus] = {'stop': True, 'turn': 1, 'can_return_stop': True}
                                            main_stop_list.append(bus)
                                        else:
                                            dec_dict[bus] = {'stop': False, 'turn': 1, 'can_return_stop': True}
                                        decide_turn[1].append(bus)
                                    else:
                                        if side_1_down + side_2_down > 0:
                                            dec_dict[bus] = {'stop': True, 'turn': 0, 'can_return_stop': False}
                                            main_stop_list.append(bus)
                                        else:
                                            dec_dict[bus] = {'stop': False, 'turn': 0, 'can_return_stop': False}
                                    dec_num += 1
                                else:
                                    if len(line.main_line[main_id]) > 0 and \
                                            len(stop_buses) + len(have_down_list) + len(main_stop_list) <= ONLY_MAIN_LINE_STOP_THRESHOLD and \
                                            cur_bus.pass_num < cur_bus.max_num:
                                        dec_dict[bus] = {'stop': True, 'turn': 0, 'can_return_stop': False}
                                        main_stop_list.append(bus)
                                    else:
                                        if side_1_down + side_2_down > 0.2:
                                            dec_dict[bus] = {'stop': True, 'turn': 0, 'can_return_stop': False}
                                            main_stop_list.append(bus)
                                        else:
                                            dec_dict[bus] = {'stop': False, 'turn': 0, 'can_return_stop': False}
                                    dec_num += 1
                            else:  # 两边都没车
                                if sum_1_up > 0.2 or sum_2_up > 0.2:
                                    if sum_1_up != sum_2_up:
                                        turn_direc = 1 if sum_1_up > sum_2_up else 2
                                    else:
                                        early_1_up = min([(min([pas.arr_t for pas in station['pool']]) if len([pas.arr_t for pas in station['pool']]) > 0 else 26 * 3600)
                                                          for station in
                                                          line.side_line[f'{main_id}#1'].side_stations.values()])
                                        early_2_up = min([(min([pas.arr_t for pas in station['pool']]) if len([pas.arr_t for pas in station['pool']]) > 0 else 26 * 3600)
                                                          for station in
                                                          line.side_line[f'{main_id}#2'].side_stations.values()])
                                        if early_1_up != early_2_up:
                                            turn_direc = 1 if early_1_up < early_2_up else 2
                                        else:
                                            turn_direc = random.randint(1, 2)
                                    if cur_bus.pass_num <= MAIN_LINE_TURN_MAX_PASS_NUM:
                                        if turn_direc == 1:
                                            if side_2_down > 0:
                                                dec_dict[bus] = {'stop': True, 'turn': turn_direc, 'can_return_stop': True}
                                                main_stop_list.append(bus)
                                            else:
                                                dec_dict[bus] = {'stop': False, 'turn': turn_direc, 'can_return_stop': True}
                                        else:
                                            if side_1_down > 0:
                                                dec_dict[bus] = {'stop': True, 'turn': turn_direc, 'can_return_stop': True}
                                                main_stop_list.append(bus)
                                            else:
                                                dec_dict[bus] = {'stop': False, 'turn': turn_direc, 'can_return_stop': True}
                                        decide_turn[turn_direc].append(bus)
                                    else:
                                        if side_1_down + side_2_down > 0.2:
                                            dec_dict[bus] = {'stop': True, 'turn': 0, 'can_return_stop': False}
                                            main_stop_list.append(bus)
                                        else:
                                            if len(line.main_line[main_id]) > 0 and \
                                                    len(stop_buses) + len(have_down_list) + len(
                                                main_stop_list) <= ONLY_MAIN_LINE_STOP_THRESHOLD and \
                                                    cur_bus.pass_num < cur_bus.max_num:
                                                dec_dict[bus] = {'stop': True, 'turn': 0, 'can_return_stop': False}
                                                main_stop_list.append(bus)
                                            else:
                                                dec_dict[bus] = {'stop': False, 'turn': 0, 'can_return_stop': False}
                                    dec_num += 1
                                else:
                                    if len(line.main_line[main_id]) > 0 and \
                                            len(stop_buses) + len(have_down_list) + len(main_stop_list) <= ONLY_MAIN_LINE_STOP_THRESHOLD and \
                                            cur_bus.pass_num < cur_bus.max_num:
                                        dec_dict[bus] = {'stop': True, 'turn': 0, 'can_return_stop': False}
                                        main_stop_list.append(bus)
                                    else:
                                        if side_1_down + side_2_down > 0.2:
                                            dec_dict[bus] = {'stop': True, 'turn': 0, 'can_return_stop': False}
                                            main_stop_list.append(bus)
                                        else:
                                            dec_dict[bus] = {'stop': False, 'turn': 0, 'can_return_stop': False}
                                    dec_num += 1

                    # 分配原地下车
                    if len(have_down_list) > 0:
                        for bus in have_down_list:
                            cur_bus = bus_info[bus]
                            sum_1_up = sum([len(station['pool'])
                                            for station in
                                            line.side_line[f'{main_id}#1'].side_stations.values()])
                            sum_2_up = sum([len(station['pool'])
                                            for station in
                                            line.side_line[f'{main_id}#2'].side_stations.values()])
                            side_1_bus_num = len([bus.bus_id for bus in bus_info.values()
                                                  if bus.able is True and bus.loc.startswith(f'{main_id}#1')])
                            side_2_bus_num = len([bus.bus_id for bus in bus_info.values()
                                                  if bus.able is True and bus.loc.startswith(f'{main_id}#2')])
                            side_1_down, side_2_down = cur_bus.stop_num_at_side_line(main_line_id=main_id)

                            if side_1_bus_num + len(decide_turn[1]) > 0.2 and side_2_bus_num + len(
                                    decide_turn[2]) > 0.2:  # 两边都有车
                                dec_dict[bus] = {'stop': True, 'turn': 0, 'can_return_stop': False}
                                dec_num += 1
                            elif side_1_bus_num + len(decide_turn[1]) > 0.2:  # 有车在#1
                                if sum_2_up > 0.2:  # 有人在#2等待
                                    dec_dict[bus] = {'stop': True, 'turn': 2, 'can_return_stop': False}
                                    decide_turn[2].append(bus)
                                    dec_num += 1
                                else:
                                    dec_dict[bus] = {'stop': True, 'turn': 0, 'can_return_stop': False}
                                    dec_num += 1
                            elif side_2_bus_num + len(decide_turn[2]) > 0.2:  # 有车在#2
                                if sum_1_up > 0.2:  # 有人在#1等待
                                    dec_dict[bus] = {'stop': True, 'turn': 1, 'can_return_stop': False}
                                    decide_turn[1].append(bus)
                                    dec_num += 1
                                else:
                                    dec_dict[bus] = {'stop': True, 'turn': 0, 'can_return_stop': False}
                                    dec_num += 1
                            else:  # 两边都没车
                                if sum_1_up > 0.2 or sum_2_up > 0.2:  # 至少有一边要下车
                                    if sum_1_up != sum_2_up:
                                        turn_direc = 1 if sum_1_up > sum_2_up else 2
                                    else:
                                        early_1_up = min([(min([pas.arr_t for pas in station['pool']]) if len([pas.arr_t for pas in station['pool']]) > 0 else 26 * 3600)
                                                          for station in
                                                          line.side_line[f'{main_id}#1'].side_stations.values()])
                                        early_2_up = min([(min([pas.arr_t for pas in station['pool']]) if len([pas.arr_t for pas in station['pool']]) > 0 else 26 * 3600)
                                                          for station in
                                                          line.side_line[f'{main_id}#2'].side_stations.values()])
                                        if early_1_up != early_2_up:
                                            turn_direc = 1 if early_1_up < early_2_up else 2
                                        else:
                                            turn_direc = random.randint(1, 2)
                                    if turn_direc == 1:
                                        dec_dict[bus] = {'stop': True, 'turn': turn_direc, 'can_return_stop': True}
                                    else:
                                        dec_dict[bus] = {'stop': True, 'turn': turn_direc, 'can_return_stop': True}
                                    decide_turn[turn_direc].append(bus)
                                    dec_num += 1
                                else:  # 两边都没人等待
                                    dec_dict[bus] = {'stop': True, 'turn': 0, 'can_return_stop': False}
                                    dec_num += 1

                assert dec_num + len(stop_buses) == len(
                    bus_group), f'{loc}, {dec_num}, {len(bus_group)}, {len(stop_buses)}'

        else:
            assert False, f'wrong decision rule!'

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
