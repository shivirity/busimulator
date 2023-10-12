# -*- coding: utf-8 -*-
"""问题的定义详见MyProblem.py。
在执行脚本main.py中设置PoolType字符串来控制采用的是多进程还是多线程。
注意：使用多进程时，程序必须以“if __name__ == '__main__':”作为入口，
      这是multiprocessing的多进程模块的硬性要求。
"""
import numpy as np

from MyProblem import MyProblem  # 导入自定义问题接口

import geatpy as ea  # import geatpy

# import os
# import sys
# sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

if __name__ == '__main__':
    # 实例化问题对象
    problem = MyProblem(
        PoolType=None)  # 设置采用多线程，若修改为: PoolType = 'Process'，则表示用多进程
    population = ea.Population(Encoding='RI', NIND=8)
    # population.Chrom = np.array([[1, 2, 1, 2, 3, 3, 2, 1, 12, 8, 8, 12, 14, 11, 12, 12] for _ in range(8)])
    # 构建算法
    algorithm = ea.soea_DE_rand_1_bin_templet(
        problem,
        population,
        MAXGEN=10,  # 最大进化代数。
        logTras=1,  # 表示每隔多少代记录一次日志信息，0表示不记录。
        trappedValue=1e-6,  # 单目标优化陷入停滞的判断阈值。
        maxTrappedCount=20)  # 进化停滞计数器最大上限值。
    prophetVars = np.array([[2, 2, 2, 2, 2, 2, 2, 2, 13, 13, 13, 13, 13, 13, 13, 13] for _ in range(8)])
    # 求解
    res = ea.optimize(algorithm,
                      verbose=True,
                      prophet=prophetVars,
                      drawing=1,
                      outputMsg=True,
                      drawLog=False,
                      saveFlag=True)
    # 输出结果
