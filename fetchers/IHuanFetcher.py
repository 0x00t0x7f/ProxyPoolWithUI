# encoding: utf-8

from fetchers.BaseFetcher import BaseFetcher
import requests
from pyquery import PyQuery as pq
import re

class IHuanFetcher(BaseFetcher):
    """
    https://ip.ihuan.me/
    爬这个网站要温柔点，站长表示可能会永久关站
    """

    def fetch(self):
        """
        执行一次爬取，返回一个数组，每个元素是(protocol, ip, port)，portocal是协议名称，目前主要为http
        返回示例：[('http', '127.0.0.1', 8080), ('http', '127.0.0.1', 1234)]
        """

        proxies = []
        ip_regex = re.compile(r'^\d+\.\d+\.\d+\.\d+$')
        port_regex = re.compile(r'^\d+$')

        pending_urls = ['https://ip.ihuan.me/']
        while len(pending_urls) > 0:
            url = pending_urls[0]
            pending_urls = pending_urls[1:]

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
            try:
                html = requests.get(url, headers=headers, timeout=10, verify=False).text
            except Exception as e:
                print('ERROR in ip.ihuan.me:' + str(e))
                continue
            doc = pq(html)
            for line in doc('tbody tr').items():
                tds = list(line('td').items())
                if len(tds) == 10:
                    ip = tds[0].text().strip()
                    port = tds[1].text().strip()
                    if re.match(ip_regex, ip) is not None and re.match(port_regex, port) is not None:
                        self.proxies.append(('http', ip, int(port)))
            
            if url.endswith('/'): # 当前是第一页，解析后面几页的链接
                for item in list(doc('.pagination a').items())[1:-1]:
                    href = item.attr('href')
                    if href is not None and href.startswith('?page='):
                        pending_urls.append('https://ip.ihuan.me/' + href)


if __name__ == '__main__':
    f = IHuanFetcher()
    ps = f.fetch()
    print(ps)