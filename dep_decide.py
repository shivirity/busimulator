from consts import LARGE_BUS, SMALL_CAB, SIM_END_T


class dep_decider:

    def __init__(self, sim_mode: str = 'single'):
        assert sim_mode in ['baseline', 'single', 'fish_bone']
        self.mode = sim_mode
        self.last_dep = None

    def can_dep(self, cur_t: int):
        """判断是否发车"""
        # todo
        if self.mode == 'baseline':
            if cur_t <= SIM_END_T:
                return True if (cur_t - self.last_dep >= 10 * 60) else False
            else:
                return False
        elif self.mode == 'single':
            pass
        else:
            pass

    def decide(self):
        """判断发车数量(num of cab)"""
        # todo
        if self.mode == 'baseline':
            return 1, LARGE_BUS
        elif self.mode == 'single':
            pass
        else:
            pass
