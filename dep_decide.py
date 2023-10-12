from consts import LARGE_BUS, SMALL_CAB, DEP_DURATION, LAST_BUS_T


class DepDecider:

    def __init__(self, sim_mode: str = 'single', dep_duration: list = None, dep_num: list = None):
        assert sim_mode in ['baseline', 'single', 'multi']
        self.mode = sim_mode
        self.last_dep = None
        self.dep_duration_list = list(dep_duration) if dep_duration is not None else None
        self.dep_num_list = list(dep_num) if dep_num is not None else None

    def can_dep(self, cur_t: int):
        """判断是否发车"""
        if self.mode == 'baseline':
            if cur_t <= LAST_BUS_T:
                return True if (cur_t - self.last_dep >= DEP_DURATION) else False
            else:
                return False
        elif self.mode == 'single':
            if cur_t <= LAST_BUS_T:
                return True if (cur_t - self.last_dep >= self.dep_duration_list[int(cur_t/3600)]) else False
            else:
                return False
        else:
            pass

    def decide(self, cur_t: int):
        """
        判断发车数量(num of cab)

        :param cur_t: 当前时间（s）
        :return: 发车数量，车厢容量
        """
        if self.mode == 'baseline':
            return 1, LARGE_BUS
        elif self.mode == 'single':
            return self.dep_num_list[int(cur_t/3600)], SMALL_CAB
        else:
            pass
