PASSENGER_SPEED = 1.4  # 乘客速度(m/s)

# use seconds in timer

SIM_START_T = 6 * 3600  # 仿真开始时间
SIM_END_T = 21.5 * 3600
LAST_BUS_T = 22 * 3600  # 最后一班车发车时间
END_T = 26 * 3600  # 仿真最晚结束时间

EARLY_HIGH_START_T = 7 * 3600  # 早高峰时间段开始时间
EARLY_HIGH_END_T = 9 * 3600  # 早高峰时间段结束时间
NOON_START_T = 11 * 3600  # 中午时间段开始时间
NOON_END_T = 13 * 3600  # 中午时间段结束时间
LATE_HIGH_START_T = 17 * 3600  # 晚高峰时间段开始时间
LATE_HIGH_END_T = 19 * 3600  # 晚高峰时间段结束时间

# case config
TEST_LINE = 810  # 案例信息
DIRECTION = 0  # 案例方向
MIN_STEP = 2  # 最小步长（秒）

# capacity of bus
LARGE_BUS = 90  # (31/90) 传统公交车容量
LARGE_BUS_SEAT = 31  # 传统公交车座位数
SMALL_CAB = 20  # (10/20) 模块化公交容量
SMALL_CAB_SEAT = 10  # 模块化公交座位数

# enter & leave of station
OLD_STOP_T_NORM = 9 + 15 + 9  # 原有进站时间（正常）
OLD_STOP_T_HIGH = 10 + 30 + 10  # 原有进站时间（高峰）
NEW_STOP_T_NORM = 8 + 10 + 8  # 新进站时间（正常）
NEW_STOP_T_HIGH = 9 + 20 + 9  # 新进站时间（高峰）

# power consumption
CONSUMP_SPEED_OLD = 52.5 / 100000  # 传统公交车功耗（速度法）
CONSUMP_SPEED_NEW = 25.6 / 100000  # 模块化公交车功耗（速度法）
CONSUMP_CONDITION_OLD = 98.4 / 100000  # 传统公交车功耗（条件法）
CONSUMP_CONDITION_NEW = 39 / 100000  # 模块化公交车功耗（条件法）

# wage
DRIVER_WAGE_OLD = 120000
DRIVER_WAGE_NEW = 100000

# departure duration
DEP_DURATION = 10 * 60  # 10 * 60

# ratio of max stop capacity to handle demand (mode='single')
RATE_MAX_STOP = 1

# max number of stations in the last part of the bus in separation decision (mode='single')
MAX_SEP_STATIONS = 1  # 1 means only separate passengers who get off at next station/stop

# travel distance fix between stations
DIS_FIX = 50

# comb and sep consts

# ------- sep decision const ------
MIN_SEP_PASS_NUM = 0  # 下车人数下限(in sep) (single: 0)
MIN_SEP_PASS_NUM_MULTI = 0  # 下车人数下限(in separation)
# ------- setting const -------
SEP_DURATION = 14  # separation 的预期时间
SEP_DIST = 155  # separation 的预期距离

# ------- comb decision const ------
RATE_COMB_ROUTE = 0.5  # in [0, 1], 预期结合的距离间隔(in combination), 越大代表对距离越宽容
RATE_COMB_ROUTE_MULTI = 0.5
RATE_FRONT_PASS = 0.3  # combination 时前车内n站内要下车的占比
RATE_FRONT_PASS_MULTI = 0.3  # 0.9
RATE_REAR_PASS = 0.5  # combination 时后车n站后要下车的占比
RATE_REAR_PASS_MULTI = 0.5  # 0.9
COMB_FORE_STA = 2  # combination 决策时预期向前的站点数
COMB_FORE_STA_MULTI = 2  # 3
# ------- setting const -------
COMB_DURATION = 22  # combination 的预期时间
COMB_DIST = 183  # combination 的预期距离

# multi-mode consts
# down_first
MAIN_LINE_STOP_TURN_THRESHOLD = 2  # 主线站点转向阈值人数
MAIN_LINE_STOP_TURN_RATE_THRESHOLD = 0.2  # 主线站点转向阈值比例
# up first
MAIN_LINE_TURN_MAX_PASS_NUM = 9  # 主线站点转向最大人数

ONLY_MAIN_LINE_STOP_THRESHOLD = 0  # 主线站点停站的等待车辆数阈值

# crowd mark consts
INTERVAL = 10 * 60

# different days
DAY = 2

# (11, 14): 4%, (10, 14): 10%, (6, 14): 28%, (4, 14): 51%

# 10-15
# can turn at peak: 10(12%), 8(20%), 7(28%)
# cannot turn at peak: 9(10%), 6(21%), 5(27%)
# 10-19
# can turn at peak: 11(11%), 8(22%), 7(28%)
# cannot turn at peak: 10(9%), 7(20%), 5(31%)
# 10-02
# can turn at peak: 10(9%), 7(23%), 6(32%)
# cannot turn at peak: 8(10%), 6(20%), 5(26%)

NUM_UB = 100  # 100
NUM_LB = 8
CAN_TURN_AT_PEAK_HOURS = False  # 是否在高峰期可以转向支线
