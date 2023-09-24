from env.bus import Bus
from env.line import Line
from env.passenger import Passenger


class route_decider:

    def __init__(self, sim_mode: str = 'single'):
        """路线决策器"""
        assert sim_mode in ['baseline', 'single', 'fish_bone']
        self.mode = sim_mode

    def decide_action(self, cur_bus: Bus, line: Line):
        """
        决策车辆在当前站的上下客以及下一站的车辆决策
        # 这里要当前车辆信息，路线信息，前车决策信息

        :param cur_bus:
        :param line:
        :return:
        """
        # todo
        if self.mode == 'baseline':
            cur_station = int(cur_bus.loc.split('@')[0])
            if cur_bus.is_to_stop(station=cur_station) or len(line.main_line[cur_station]) > 0:
                return {'stop': True, }
            else:
                return {'stop': False, }
        elif self.mode == 'single':
            pass
        else:
            pass

    @staticmethod
    def time2dec(loc: str, state: bool):
        """
        是否到达决策时间点（决策在进站前进行，静态决策）

        :param loc: 车辆（bus）位置
        :param state: 车辆状态，是否停站等待中
        :return:
        """
        return (not state) and loc.split('@')[1] == '0'
