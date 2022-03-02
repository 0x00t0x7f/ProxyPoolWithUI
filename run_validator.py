# encoding: utf-8
"""
验证器逻辑
"""

import random
import threading
from loger import log
from retry import retry
from func_timeout import func_set_timeout
import time
import requests
from db import conn
from config import PROC_VALIDATOR_SLEEP, VALIDATE_THREAD_NUM, VALIDATE_TARGETS_CN, VALIDATE_TARGETS_OVERSEA
from config import VALIDATE_TIMEOUT, VALIDATE_MAX_FAILS, VALIDATE_TIME_GAP


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
    while True:
        threads = []
        proxies = conn.getToValidate(VALIDATE_THREAD_NUM)
        for proxy in proxies:
            thread = threading.Thread(target=validate_thread, args=(proxy,))
            threads.append(thread)
            thread.start()
            any_start = True

        if not any_start:
            time.sleep(PROC_VALIDATOR_SLEEP)
        else:
            log(f"验证完成{len(proxies)}")


def validate_thread(proxy):
    """
    验证函数，这个函数会在一个线程中被调用
    in_que: 输入队列，用于接收验证任务
    out_que: 输出队列，用于返回验证结果
    in_que和out_que都是线程安全队列，并且如果队列为空，调用in_que.get()会阻塞线程
    """
    @func_set_timeout(VALIDATE_MAX_FAILS*VALIDATE_TIMEOUT*1.5)
    @retry(tries=VALIDATE_MAX_FAILS)
    def validate_once(proxy, targets):
        """[随机选择一个验证目标验证一次代理]

        Returns:
            [bool]: [代理是否可用]
            [float]: [可用则返回延时， 否则返回None]
        """
        @func_set_timeout(VALIDATE_TIMEOUT*1.1)
        def req(target, proxy):
            r = requests.get(
                url=target["url"],
                timeout=VALIDATE_TIMEOUT,
                proxies={
                    'http': f'{proxy.protocol}://{proxy.ip}:{proxy.port}',
                    'https': f'{proxy.protocol}://{proxy.ip}:{proxy.port}'
                }
            )
            r.raise_for_status()
            return r

        # 获取验证目标
        target = random.choice(targets)
        # 记录验证耗时
        start_time = time.time()
        r = req(target, proxy)

        # 延时 加 传输耗时 对评估代理可用性更有价值
        time_cost = time.time() - start_time

        # start_time = time.time()
        # r = requests.get(
        #     url= 'http://47.113.219.219:8000/proxy_tool/',
        #     timeout=VALIDATE_TIMEOUT,
        #     proxies={
        #         'http': f'{proxy.protocol}://{proxy.ip}:{proxy.port}',
        #         'https': f'{proxy.protocol}://{proxy.ip}:{proxy.port}'
        #     }
        # )
        # r.raise_for_status()

        # 可用 = 整体耗时 < 预设耗时 and 状态码正常
        success = r.status_code in target["codes"] and time_cost <= VALIDATE_TIMEOUT
        return success, int(time_cost*1000) if success else 9999


    # 尝试验证代理 返回可用状态与 异常则返回不可用状态
    try:
        success_cn, latency_cn = validate_once(proxy, VALIDATE_TARGETS_CN)
    except Exception:
        success_cn, latency_cn = False, 9999

    try:
        success_oversea, latency_oversea = validate_once(proxy, VALIDATE_TARGETS_OVERSEA)
    except Exception:
        success_oversea, latency_oversea = False, 9999

    # 只要一个区域验证成功则认为成功
    proxy.validated = success_cn or success_oversea
    # 记录延迟与 验证时间
    proxy.latency_cn = latency_cn
    proxy.latency_oversea = latency_oversea
    proxy.validate_time = time.time()
    # 计算下次验证时间
    proxy.to_validate_time = proxy.validate_time + VALIDATE_TIME_GAP*(1 if proxy.validated else proxy.validate_failed_count ** 2)
    # 根据是否成功 更新验证失败的次数
    proxy.validate_failed_count = 0 if proxy.validated else proxy.validate_failed_count + 1

    # 如果失败次数大于100 则放弃该代理
    if proxy.validate_failed_count > 10:
        log(f"del {proxy}", 2)
        proxy.delete()
    else:
        proxy.save()


if __name__ == '__main__':
    main()
