import asyncio
import time
from urllib.parse import urljoin

import aiohttp
from lxml import html
from ruamel.yaml import YAML

# 存儲已訪問連結的字典
visited_links = {}

# 存儲錯誤連結的字典
error_links = {}


async def check_link(url, session, depth=0, retries=3, max_depth=2):
    if url in visited_links:
        return

    visited_links[url] = "Processing"

    try:
        async with session.get(url, timeout=10) as response:
            status = response.status
            visited_links[url] = status

            if status == 200:
                content_type = response.headers.get('Content-Type', '')
                if content_type.startswith('text/html'):
                    content = await response.text()
                    tree = html.fromstring(content)

                    for link in tree.xpath('//a[@href] | //img[@src]'):
                        link_url = link.attrib.get('href') or link.attrib.get('src')
                        if link_url and not link_url.startswith(('http', '#', 'javascript', 'mailto', 'data:image')):
                            full_url = urljoin(url, link_url)
                            await check_link(full_url, session, depth + 1, retries, max_depth)
    except asyncio.TimeoutError:
        if retries > 0:
            await check_link(url, session, depth, retries - 1, max_depth)
        else:
            error_links[url] = {
                "掃描層數": depth,
                "網址": url,
                "失效連結": url,
                "回應狀態碼或錯誤原因": "Timeout Error",
            }
            visited_links[url] = "Timeout Error"
    except ConnectionResetError as e:
        # 捕獲連接重置錯誤
        error_links[url] = {"掃描層數": depth, "網址": url, "失效連結": url, "回應狀態碼或錯誤原因": str(e)}
        visited_links[url] = str(e)
    except Exception as e:
        # 捕獲所有類型的異常
        error_links[url] = {"掃描層數": depth, "網址": url, "失效連結": url, "回應狀態碼或錯誤原因": str(e)}
        visited_links[url] = str(e)
    finally:
        if depth >= max_depth:
            visited_links[url] = "Depth Limit Reached"


async def main(urls, max_depth=2):
    async with aiohttp.ClientSession() as session:
        tasks = [check_link(url, session, max_depth=max_depth) for url in urls]
        await asyncio.gather(*tasks)


if __name__ == "__main__":
    start_time = time.time()
    urls = [
        "https://www.ncut.edu.tw/",
        "https://cc.ncut.edu.tw/",
    ]
    max_depth = 3  # 您可以在這裡設定掃描的最大深度
    asyncio.run(main(urls, max_depth))
    end_time = time.time()
    print("Scanning took {:.2f} seconds.".format(end_time - start_time))

    print("Total Error Links:", len(error_links))
    print("Total Visited Links:", len(visited_links))

    yaml = YAML()
    with open("error_links.yaml", "w") as error_file:
        yaml.dump(error_links, error_file)

    with open("visited_links.yaml", "w") as visited_file:
        yaml.dump(visited_links, visited_file)
