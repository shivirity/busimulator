# -*- coding: utf-8 -*-
# import sys
import numpy as np
import geatpy as ea
from opt_consts import *

from multiprocessing import Pool as ProcessPool
import multiprocessing as mp
from multiprocessing.dummy import Pool as ThreadPool

import os
import sys
# sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from sim import read_in_for_opt, Sim


class MyProblem(ea.Problem):  # 继承Problem父类

    def __init__(self, PoolType):
        name = 'MyProblem'  # 初始化name（函数名称，可以随意设置）
        M = 1  # 初始化M（目标维数）
        maxormins = [1]  # 最小化
        Dim = 16  # 初始化Dim（决策变量维数）
        varTypes = [1] * Dim  # 初始化varTypes（决策变量的类型，0表示实数，1表示整数）
        lb = [1 for _ in range(int(Dim / 2))] + [8 for _ in range(int(Dim / 2))]  # 决策变量下界， [dep_num + dep_duration]
        ub = [3 for _ in range(int(Dim / 2))] + [15 for _ in range(int(Dim / 2))]  # 决策变量上界， [dep_num + dep_duration]
        lbin = [1 for _ in range(Dim)]  # 决策变量下边界，[dep_num + dep_duration]
        ubin = [1 for _ in range(Dim)]  # 决策变量上边界，[dep_num + dep_duration]
        # 调用父类构造方法完成实例化
        ea.Problem.__init__(self, name, M, maxormins, Dim, varTypes, lb, ub, lbin, ubin)

        self.data = read_in_for_opt(way='total', fractile=None)

        # 设置用多线程还是多进程
        self.PoolType = PoolType
        if self.PoolType == 'Thread':
            self.pool = ThreadPool(10)  # 设置池的大小
        elif self.PoolType == 'Process':
            num_cores = int(mp.cpu_count())  # 获得计算机的核心数
            self.pool = ProcessPool(num_cores)  # 设置池的大小
        else:
            assert PoolType is None
            self.PoolType = None

    def evalVars(self, Vars):
        N = Vars.shape[0]
        args = list(
            zip(list(range(N)), [Vars] * N, [self.data] * N))
        if self.PoolType is None:
            result_list = []
            for i in range(N):
                result_list.append(subAimFunc(args[i]))
            f = np.array([val[0] for val in result_list]).reshape((-1, 1))
            CV = np.array([val[1] for val in result_list]).reshape((-1, 1))
        elif self.PoolType == 'Thread':
            result_list = list(self.pool.map(subAimFunc, args))
            f = np.array([val[0] for val in result_list]).reshape((-1, 1))
            CV = np.array([val[1] for val in result_list]).reshape((-1, 1))
        elif self.PoolType == 'Process':
            result = self.pool.map_async(subAimFunc, args)
            result.wait()
            result_list = list(result.get())
            f = np.array([val[0] for val in result_list]).reshape((-1, 1))
            CV = np.array([val[1] for val in result_list]).reshape((-1, 1))
        else:
            assert False, 'self.PoolType is wrong!'

        return f, CV


def subAimFunc(args):
    i = args[0]  # 种群编号
    Vars = args[1]
    data = args[2]
    var = Vars[i, :]
    dep_num_var = [0 for _ in range(6)] + [val for val in var[:8] for _ in range(2)] + [1, 1]
    dep_duration_var = [0 for _ in range(6)] + [val * 60 for val in var[8:] for _ in range(2)] + [var[-1] * 60, var[-1] * 60]

    multi_dec_rule = 'up_first'
    data['dep_num_list'] = dep_num_var
    data['dep_duration_list'] = dep_duration_var
    sim = Sim(**data, sim_mode='multi_order', multi_dec_rule=multi_dec_rule, record_time=None)
    sim.can_reorg = True
    sim.print_log = False

    sim.run()
    obj = sim.get_statistics()['power consumption(condition, kWh)']
    avg_t = sim.get_statistics()['avg_travel_t(full, min)']
    # travel_t = sim.get_statistics()['avg_travel_t(full, min)']
    # t_cond = -1 if (LB_AVG_T <= avg_t < UB_AVG_T and travel_t <= UB_TRAVEL_T) else 1
    t_cond = -1 if LB_AVG_T <= avg_t < UB_AVG_T else 1
    return obj, t_cond
