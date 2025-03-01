# encoding: utf-8

from fetchers.BaseFetcher import BaseFetcher
import requests
from pyquery import PyQuery as pq
import re


class IP66Fetcher(BaseFetcher):
    """
    http://www.66ip.cn/
    """

    def fetch(self):
        """
        执行一次爬取，返回一个数组，每个元素是(protocol, ip, port)，portocal是协议名称，目前主要为http
        返回示例：[('http', '127.0.0.1', 8080), ('http', '127.0.0.1', 1234)]
        """

        urls = []
        for areaindex in range(10):
            for page in range(1, 6):
                if areaindex == 0:
                    url = f'http://www.66ip.cn/{page}.html'
                else:
                    url = f'http://www.66ip.cn/areaindex_{areaindex}/{page}.html'
                urls.append(url)

        proxies = []
        ip_regex = re.compile(r'^\d+\.\d+\.\d+\.\d+$')
        port_regex = re.compile(r'^\d+$')

        for url in urls:
            headers = {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
                'Accept-Encoding': 'gzip, deflate',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Pragma': 'no-cache',
                'Upgrade-Insecure-Requests': '1',
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/79.0.3945.130 Chrome/79.0.3945.130 Safari/537.36'
            }
            html = requests.get(url, headers=headers, timeout=10).text
            doc = pq(html)
            for line in doc('table tr').items():
                tds = list(line('td').items())
                if len(tds) == 5:
                    ip = tds[0].text().strip()
                    port = tds[1].text().strip()
                    if re.match(ip_regex, ip) is not None and re.match(port_regex, port) is not None:
                        self.proxies.append(('http', ip, int(port)))
        

if __name__ == '__main__':
    f = IP66Fetcher()
    f.fetch()
