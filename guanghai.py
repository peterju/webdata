import asyncio
import os

import aiohttp
from lxml import html

# 這個程式碼使用了Python的非同步套件asyncio和aiohttp，以非同步的方式發送網路請求並處理回應。lxml用於解析HTML內容。
# 在程式碼中，首先定義了一個fetch_content函式來從網路上獲取內容。
# 接著，parse_content函式使用fetch_content函式獲取網頁內容，
# 並使用lxml來解析標題和內容。
# 最後，在main函式中，使用asyncio.gather來等待所有網頁的解析任務完成，並將結果存儲在字典中，
# 再將結果轉換為HTML。
# https://myapollo.com.tw/blog/aiohttp-client/

# 要讀取的網址列表
base_url = "https://www.amrtf.org/zh-hant/clear-moonlight-great-ocean-"
urls = [f"{base_url}{i:04d}/" for i in range(1, 485)]


async def fetch_content(url: str) -> str:
    '''獲取網頁內容'''
    timeout = aiohttp.ClientTimeout(total=10)  # 設置超時時間為10秒
    async with aiohttp.ClientSession(timeout=timeout) as session:  # 建立一個 session 物件
        try:
            async with session.get(url) as response:  # 使用 session 物件發送網路請求
                content = await response.text()  # 等待網路回應並返回回應內容
                return content
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
            return None


async def parse_content(url: str) -> tuple[str, list[str]]:
    '''解析網頁內容'''
    content = await fetch_content(url)  # 獲取網頁內容
    for i in range(3):
        if content is None:
            print(f"{url} 內容抓取失敗，嘗試重新抓取 {i + 1} 次")
            content = await fetch_content(url)
        else:
            break
    if content is None:
        print(f"{url} 內容抓取失敗，請檢查網路連線或網址是否正確，並請稍後再試。")
        exit(1)
    # 使用lxml解析網頁內容，僅抓取指定標籤內容
    tree = html.fromstring(content)  # 使用lxml解析HTML內容
    title = tree.xpath('//title/text()')[0]  # 抓取標題內容
    title = title.split("–")[0].strip()  # 將標題內容分割，並取出第一部分
    # 抓取 <span class='lrc 開頭的標籤內容 與 <p class="no-indent"> 之後的 <p> 標籤內容
    span_and_p_contents = tree.xpath(
        "//span[starts-with(@class, 'lrc')]/text() | //p[@class='no-indent']/following-sibling::p/text() | //span[starts-with(@class, 'scripture-kai')]/text() | //span[starts-with(@class, 'scripture-fangsong')]/text()"
    )
    # 將\n換行符號去除
    span_and_p_contents = [content.strip() for content in span_and_p_contents if content.strip()]
    return title, span_and_p_contents  # 返回標題和內容


async def generate_html_pages(results_dict: dict[str, list[str]], items_per_page: int = 5):
    '''產生網頁'''
    html_top = '''<!DOCTYPE html>
    <html lang="zh-hant-TW">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>廣海明月</title>
    </head>
    <body>'''

    page_count = len(results_dict) // items_per_page + (1 if len(results_dict) % items_per_page != 0 else 0)
    os.makedirs("html_result_廣海", exist_ok=True)  # 如果 html_result_廣海 子目錄不存在，則建立之
    for page_idx in range(page_count):
        html_content = html_top
        start_idx = page_idx * items_per_page
        end_idx = min((page_idx + 1) * items_per_page, len(results_dict))
        for idx, (key, value) in enumerate(list(results_dict.items())[start_idx:end_idx], start=1):
            html_content += f"\n    <h2>{key}</h2>\n    <p>"  # 取出key值當作標題
            for item in value:
                html_content += f"{item}"  # 取出value值當作內容
            html_content += '</p>'
        html_content += "\n</body>\n</html>"
        with open(f"html_result_廣海/guanghai_{page_idx + 1}.html", "w", encoding="utf-8") as file:
            file.write(html_content)

    # 產生主頁
    index_content = html_top
    index_content += "\n<h1>廣海明月</h1>\n<ul>"
    for page_idx in range(page_count):
        start_item = page_idx * items_per_page + 1
        end_item = min((page_idx + 1) * items_per_page, len(results_dict))
        index_content += (
            f'\n    <li><a href="guanghai_{page_idx + 1}.html">第 {start_item:04d}-{end_item:04d} 講</a></li>'
        )
    index_content += "\n</ul>\n</body>\n</html>"
    with open("html_result_廣海/guanghai.html", "w", encoding="utf-8") as file:
        file.write(index_content)
    print("主頁與子頁皆已生成，結果保存在 html_result_廣海 目錄中。")


async def generate_text_files(results_dict: dict[str, list[str]], items_per_file: int = 5):
    '''將結果寫入文字檔'''
    # 建立存放文字檔的子目錄
    os.makedirs("text_result_廣海", exist_ok=True)  # 如果 text_result_廣海 子目錄不存在，則建立之

    for idx, (key, value) in enumerate(results_dict.items(), start=1):
        # 每 items_per_file 個 item 寫入一個文字檔
        if (idx - 1) % items_per_file == 0:
            file_idx = (idx - 1) // items_per_file + 1
            with open(f"text_result_廣海/guanghai_{file_idx}.txt", "w", encoding="utf-8") as file:
                file.write(f"第 {idx:04d} 講：{key}\n")
        else:
            with open(f"text_result_廣海/guanghai_{file_idx}.txt", "a", encoding="utf-8") as file:
                file.write(f"\n第 {idx:04d} 講：{key}\n")
        # 將換行符號消除，再寫入文件
        value_without_newlines = ''.join(value)
        with open(f"text_result_廣海/guanghai_{file_idx}.txt", "a", encoding="utf-8") as file:
            file.write(f"{value_without_newlines}\n")
    print("文字檔已生成，結果保存在 text_result_廣海 目錄中。")


async def main() -> dict[str, list[str]]:
    '''主函式'''
    results = {}
    tasks = [parse_content(url) for url in urls]  # 將解析任務加入任務列表

    # 等待所有非同步任務完成
    completed_tasks = await asyncio.gather(*tasks)  # 使用asyncio.gather等待所有網頁的解析任務完成
    for title, content in completed_tasks:  # 將結果存儲在字典中
        results[title] = content  # 將標題和內容存儲在字典中

    await asyncio.gather(generate_html_pages(results, items_per_page=5), generate_text_files(results, items_per_file=5))
    return results  # 返回結果


loop = asyncio.get_event_loop()  # 建立一個事件迴圈
results = loop.run_until_complete(main())  # 使用事件迴圈執行main函式，獲取結果

# 檢查 urls 的數量與成功解析的 results 的數量是否相同
assert len(urls) == len(results), "有部分網頁內容抓取或解析失敗，請重新執行抓取作業。"
