class Bus:

    def __init__(self, cab_num: int, max_num_list: list, cab_id: list, bus_id: int):
        self.cab_num = cab_num  # 车厢数量
        # self.pass_num_list = [0 for _ in range(cab_num)]  # 乘客数量, list
        self.pass_list = [[] for _ in range(cab_num)]  # 储存乘客对象，list
        self.max_num_list = list(max_num_list)
        self.cab_id = cab_id  # 包含的 cab 编号
        self.bus_id = bus_id  # 单一 bus id

        self.state = 'start'  # in ['start, end']
        self.loc = '1@0'  # 初始化位置在起始站点

        # 决策过程相关
        self.to_stop = False  # 是否要在站点停留
        self.is_waiting = False  # 是否在上下客的等待过程中
        self.stop_count = 0

        # 行驶过程相关
        self.running = False  # 是否正在行驶
        self.run_next = '1@5'
        self.time_count = 0

    @property
    def loc_num(self):
        """仅用于决策顺序排序使用"""
        loc_1, loc_2 = self.loc.split('@')
        return int(loc_1) + int(loc_2) / 10

    def is_to_stop(self, station):
        """当前车辆上有需要下车的乘客"""
        pass_list = [i for j in self.pass_list for i in j]
        for passenger in pass_list:
            if passenger.end_loc == station:
                return True
        else:
            return False
