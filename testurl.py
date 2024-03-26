import asyncio
import time
from urllib.parse import urljoin, urlparse

import aiohttp
from aiohttp import ClientError
from lxml import html
from ruamel.yaml import YAML

# 定義最大遞迴深度
MAX_DEPTH = 3


async def fetch(session: aiohttp.ClientSession, url: str) -> tuple:
    """
    異步獲取 URL 的內容

    Args:
        session (aiohttp.ClientSession): aiohttp ClientSession 物件。
        url (str): 要獲取的 URL。

    Returns:
        tuple: 包含 HTML 內容、基礎 URL 和錯誤訊息的元組。
    """
    try:
        print(f"掃描連結：{url}")
        # 如果 URL 已經掃描過，直接返回之前的結果
        if url in scanned_urls:
            return scanned_urls[url]

        async with session.get(url) as response:
            if response.status == 200:
                # 嘗試使用不同的字符編碼解碼內容
                for encoding in ['utf-8', 'gbk', 'big5']:
                    try:
                        content = await response.read()
                        html_text = content.decode(encoding)
                        # 如果成功解碼，返回HTML文本、基礎URL和空的錯誤消息
                        result = html_text, url, None
                        # 保存至 scanned_urls
                        scanned_urls[url] = result
                        return result
                    except UnicodeDecodeError:
                        pass
                # 如果所有的解碼方式都失敗，返回空的HTML文本、URL和錯誤消息
                result = None, url, '無法解碼內容'
                scanned_urls[url] = result
                return result
            else:
                # 因非 200 HTTP 狀態而獲取失敗
                result = None, url, f"HTTP 狀態 {response.status}"
                scanned_urls[url] = result
                return result
    except ClientError as e:
        # 因客戶端錯誤而獲取失敗
        result = None, url, str(e)
        scanned_urls[url] = result
        return result


async def find_links(session: aiohttp.ClientSession, url: str, base_url: str, depth: int = 0) -> tuple:
    """
    遞迴尋找網頁內的連結

    Args:
        session (aiohttp.ClientSession): aiohttp ClientSession 物件。
        url (str): 網頁的 URL。
        base_url (str): 基礎 URL。
        depth (int): 目前遞迴的深度。

    Returns:
        tuple: 包含具有子連結和不具子連結的連結列表以及基礎 URL 的元組。
    """
    try:
        # 如果遞迴深度超過最大深度，直接返回空列表和空的基礎 URL
        if depth >= MAX_DEPTH:
            return [], [], None

        # 檢查 URL 的主要域是否與基礎 URL 的主要域相同
        if urlparse(url).netloc != urlparse(base_url).netloc:
            # 如果主要域不同，僅掃描該連結
            _, _, error_message = await fetch(session, url)
            return [], [], error_message

        html_text, _, error_message = await fetch(session, url)
        if error_message:
            return None, [], error_message

        tree = html.fromstring(html_text)
        links_with_sublinks = []
        links_without_sublinks = []

        for element, attribute in [("a", "href"), ("img", "src"), ("script", "src")]:
            for link in tree.xpath(f"//{element}[@{attribute}]"):
                link_url = urljoin(base_url, link.get(attribute))
                if not any(link_url.startswith(prefix) for prefix in ['#', 'javascript', 'mailto', 'data:image']):
                    links_with_sublinks.append(link_url)
                else:
                    links_without_sublinks.append(link_url)

        return links_with_sublinks, links_without_sublinks, base_url
    except Exception as e:
        # 解析 URL 時出錯
        return None, [], str(e)


async def check_links(url: str, depth: int = 0, visited_urls: set = None) -> list:
    """
    檢查網頁中的無效連結

    Args:
        url (str): 網頁的 URL。
        depth (int): 目前遞迴的深度。
        visited_urls (set): 已訪問的 URL 集合。

    Returns:
        list: 包含深度、父 URL、無效連結和錯誤訊息的元組列表。
    """
    # 初始化已訪問的 URL 集合
    if visited_urls is None:
        visited_urls = set()

    # 檢查遞迴深度是否超過最大深度限制
    if depth >= MAX_DEPTH:
        return []

    # 如果 URL 已經訪問過，直接返回空列表
    if url in visited_urls:
        return []

    visited_urls.add(url)  # 將當前 URL 加入已訪問集合

    async with aiohttp.ClientSession() as session:
        invalid_links = []
        links_with_sublinks, _, parent_url = await find_links(session, url, url, depth)
        if links_with_sublinks is None:
            return invalid_links

        # 檢查每個有子連結的連結
        for link in links_with_sublinks:
            html_text, _, error_message = await fetch(session, link)
            if error_message:
                invalid_links.append((depth + 1, parent_url, link, error_message))

        # 遞迴檢查下一層連結
        for link in links_with_sublinks:
            invalid_links.extend(await check_links(link, depth + 1, visited_urls))

        return invalid_links


def generate_results_html(url: str, invalid_links: list) -> str:
    """
    生成單個 URL 的結果 HTML 文檔

    Args:
        url (str): 網頁的 URL。
        invalid_links (list): 包含深度、父 URL、無效連結和錯誤訊息的元組列表。

    Returns:
        str: HTML 文檔內容。
    """
    output = f"""<!DOCTYPE html>
    <html>
    <head>
    <title>無效連結</title>
    </head>
    <body>
    <h1>無效連結 - {url}</h1>
    <table border='1'>
    <tr>
    <th>深度</th>
    <th>父 URL</th>
    <th>無效連結</th>
    <th>錯誤訊息</th>
    </tr>
    """
    for depth, parent_url, invalid_link, error_message in invalid_links:
        output += f"""
        <tr>
        <td>{depth}</td>
        <td>{parent_url}</td>
        <td>{invalid_link}</td>
        <td>{error_message}</td>
        </tr>
        """
    output += """
    </table>
    </body>
    </html>
    """
    return output


async def main() -> None:
    '''非同步主函式'''
    start_time = time.time()
    urls = [
        "https://www.ncut.edu.tw/",
        "https://cc.ncut.edu.tw/",
        # 需要更多的 URL
    ]

    for url in urls:
        print(f"掃描網頁：{url}")
        invalid_links = await check_links(url)

        output_file = f"invalid_links_{urlparse(url).netloc.replace('.', '_')}.html"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(generate_results_html(url, invalid_links))

    # 篩選出狀態為 200 的連結
    valid_urls = {url: result for url, result in scanned_urls.items() if result[1] == 200}
    # 將有效連結存儲為 YAML 檔案
    with open('scanned_urls.yaml', 'w') as yaml_file:
        yaml.dump(valid_urls, yaml_file)

    end_time = time.time()
    elapsed_time = end_time - start_time
    formatted_time = time.strftime("%H:%M:%S", time.gmtime(elapsed_time))
    print(f"掃描完成，總花費時間：{formatted_time}")


def read_scanned_urls() -> dict:
    """
    讀取已掃描的 URL 和其結果，如果不存在則返回空字典。

    Returns:
        dict: 已掃描的 URL 和其結果。
    """
    try:
        with open('scanned_urls.yaml', 'r') as yaml_file:
            return yaml.load(yaml_file)
    except FileNotFoundError:
        return {}


# 程式主體
yaml = YAML()  # 載入yaml處理模組
scanned_urls = read_scanned_urls()  # 讀取已掃描的 URL 和其結果
asyncio.run(main())
