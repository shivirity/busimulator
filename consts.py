PASSENGER_SPEED = 1.4

# use seconds in timer

SIM_START_T = 6 * 3600
SIM_END_T = 21.5 * 3600
LAST_BUS_T = 22 * 3600
END_T = 26 * 3600

# case config
TEST_LINE = 810
DIRECTION = 0
MIN_STEP = 2

# capacity of bus
LARGE_BUS = 90  # (31/90)
LARGE_BUS_SEAT = 31
SMALL_CAB = 20  # (10/20)
SMALL_CAB_SEAT = 10

# enter & leave of station
OLD_STOP_T_NORM = 9 + 15 + 9
OLD_STOP_T_HIGH = 10 + 30 + 10
NEW_STOP_T_NORM = 8 + 10 + 8
NEW_STOP_T_HIGH = 9 + 20 + 9

# power consumption
CONSUMP_SPEED_OLD = 52.5
CONSUMP_SPEED_NEW = 25.6
CONSUMP_CONDITION_OLD = 98.4
CONSUMP_CONDITION_NEW = 39

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
MIN_SEP_PASS_NUM_MULTI = 0  # 下车人数下限(in sep)
# ------- setting const -------
SEP_DURATION = 14  # sep的预期时间
SEP_DIST = 155  # sep的预期距离

# ------- comb decision const ------
RATE_COMB_ROUTE = 0.5  # in [0, 1], 预期结合的距离间隔(in comb), 越大代表对距离越宽容
RATE_COMB_ROUTE_MULTI = 0.5
RATE_FRONT_PASS = 0.3  # 分离时前车内n站内要下车的占比
RATE_FRONT_PASS_MULTI = 0.3
RATE_REAR_PASS = 0.5  # 分离时后车n站后要下车的占比
RATE_REAR_PASS_MULTI = 0.5
COMB_FORE_STA = 2  # comb决策时预期向前的站点数
COMB_FORE_STA_MULTI = 3
# ------- setting const -------
COMB_DURATION = 22  # comb的预期时间
COMB_DIST = 183  # comb的预期距离

# multi-mode consts
MAIN_LINE_STOP_TURN_THRESHOLD = 2  # 主线站点转向阈值人数
MAIN_LINE_STOP_TURN_RATE_THRESHOLD = 0.2  # 主线站点转向阈值比例

ONLY_MAIN_LINE_STOP_THRESHOLD = 1  # 主线站点停站的等待车辆数阈值
