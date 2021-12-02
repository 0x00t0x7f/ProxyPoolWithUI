# encoding: utf-8
"""
验证器逻辑
"""

import sys
import random
import threading
from queue import Queue
import logging
import time
import requests
from func_timeout import func_set_timeout
from func_timeout.exceptions import FunctionTimedOut
from db import conn
from config import PROC_VALIDATOR_SLEEP, VALIDATE_THREAD_NUM, VALIDATE_TARGETS
from config import VALIDATE_TIMEOUT, VALIDATE_MAX_FAILS

logging.basicConfig(stream=sys.stdout, format="%(asctime)s-%(levelname)s:%(name)s:%(message)s", level='INFO')


def main():
    """
    验证器
    主要逻辑：
    创建VALIDATE_THREAD_NUM个验证线程，这些线程会不断运行
    While True:
        检查验证线程是否返回了代理的验证结果
        从数据库中获取若干当前待验证的代理
        将代理发送给前面创建的线程
    """
    logger = logging.getLogger('validator')

    in_que = Queue()
    out_que = Queue()
    running_proxies = set() # 储存哪些代理正在运行，以字符串的形式储存

    threads = []
    for _ in range(VALIDATE_THREAD_NUM):
        threads.append(threading.Thread(target=validate_thread, args=(in_que, out_que)))
    [_.start() for _ in threads]

    while True:
        out_cnt = 0
        while not out_que.empty():
            proxy, success, latency = out_que.get()
            conn.pushValidateResult(proxy, success, latency)
            uri = f'{proxy.protocol}://{proxy.ip}:{proxy.port}'
            assert uri in running_proxies
            running_proxies.remove(uri)
            out_cnt = out_cnt + 1
        if out_cnt > 0:
            logger.info(f'完成了{out_cnt}个代理的验证')

        # 如果正在进行验证的代理足够多，那么就不着急添加新代理        
        if len(running_proxies) >= VALIDATE_THREAD_NUM:
            time.sleep(PROC_VALIDATOR_SLEEP)
            continue

        # 找一些新的待验证的代理放入队列中
        added_cnt = 0
        for proxy in conn.getToValidate(VALIDATE_THREAD_NUM):
            uri = f'{proxy.protocol}://{proxy.ip}:{proxy.port}'
            # 这里找出的代理有可能是正在进行验证的代理，要避免重复加入
            if uri not in running_proxies:
                running_proxies.add(uri)
                in_que.put(proxy)
                added_cnt += 1
        
        if added_cnt == 0:
            time.sleep(PROC_VALIDATOR_SLEEP)


@func_set_timeout(VALIDATE_TIMEOUT * 2)
def validate_once(proxy):
    """
    进行一次验证，如果验证成功则返回True，否则返回False或者是异常
    """
    proxies = {
        'http': f'{proxy.protocol}://{proxy.ip}:{proxy.port}',
        'https': f'{proxy.protocol}://{proxy.ip}:{proxy.port}'
    }
    target = random.choice(VALIDATE_TARGETS)
    r = requests.get(target["url"], timeout=VALIDATE_TIMEOUT, proxies=proxies)
    return r.status_code in target["codes"]


def validate_thread(in_que, out_que):
    """
    验证函数，这个函数会在一个线程中被调用
    in_que: 输入队列，用于接收验证任务
    out_que: 输出队列，用于返回验证结果
    in_que和out_que都是线程安全队列，并且如果队列为空，调用in_que.get()会阻塞线程
    """

    while True:
        proxy = in_que.get()

        success = False
        latency = None
        for _ in range(VALIDATE_MAX_FAILS):
            try:
                start_time = time.time()
                if validate_once(proxy):
                    end_time = time.time()
                    latency = int((end_time-start_time)*1000)
                    success = True
                    break
            except Exception as e:
                pass
            except FunctionTimedOut:
                pass

        out_que.put((proxy, success, latency))
