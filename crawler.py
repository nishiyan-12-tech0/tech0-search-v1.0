"""
crawler.py — Tech0 Search v1.0
URLからWebページを取得し、タイトル・説明文・本文などを抽出する。
"""

import re
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup


# ── HTML 取得 ───────────────────────────────────────────────────────────────

def fetch_page(url: str, timeout: int = 10) -> Optional[str]:
    """
    指定URLのHTMLを取得する。

    Args:
        url    : 取得対象URL
        timeout: タイムアウト秒数

    Returns:
        HTML文字列。取得失敗時は None
    """
    try:
        # ボットと識別されないようにUser-Agentを指定する
        headers = {"User-Agent": "Tech0SearchBot/1.0 (Educational Purpose)"}
        resp = requests.get(url, headers=headers, timeout=timeout)

        # HTTPエラー（404など）は例外にする
        resp.raise_for_status()

        # 文字コードを自動検出して設定する
        resp.encoding = resp.apparent_encoding
        return resp.text

    except requests.RequestException as e:
        print(f"取得エラー: {e}")
        return None


# ── HTML 解析 ──────────────────────────────────────────────────────────────

def parse_html(html: str, url: str) -> dict:
    """
    HTMLを解析してページ情報（タイトル・説明文・本文など）を抽出する。

    Args:
        html: HTML文字列
        url : 元のURL

    Returns:
        ページ情報の辞書
    """
    soup = BeautifulSoup(html, "html.parser")

    # 不要タグを除去する（スクリプト・スタイルなど）
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    # タイトルを取得する（<title> → <h1> の順で試みる）
    title = "No Title"
    if soup.find("title"):
        title = soup.find("title").get_text().strip()
    elif soup.find("h1"):
        title = soup.find("h1").get_text().strip()

    # meta description を取得する
    description = ""
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content"):
        description = meta["content"][:200]

    # meta keywords を取得する（カンマ区切り → リストに変換）
    keywords = []
    meta_kw = soup.find("meta", attrs={"name": "keywords"})
    if meta_kw and meta_kw.get("content"):
        keywords = [kw.strip() for kw in meta_kw["content"].split(",")][:10]

    # 本文テキストを取得する（p・h1〜h6・li・tdタグの内容を結合）
    elems = soup.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "td"])
    full_text = " ".join(e.get_text().strip() for e in elems)
    full_text = re.sub(r"\s+", " ", full_text).strip()

    # ページ内のリンクを取得する（外部リンクのみ最大20件）
    links = [
        a["href"]
        for a in soup.find_all("a", href=True)
        if a["href"].startswith("http")
    ][:20]

    return {
        "url"         : url,
        "title"       : title,
        "description" : description,
        "keywords"    : keywords,
        "full_text"   : full_text,
        "word_count"  : len(full_text.split()),
        "links"       : links,
        "crawled_at"  : datetime.now().isoformat(),
        "crawl_status": "success",
    }


# ── クロール（fetch + parse のワンストップ）────────────────────────────────

def crawl_url(url: str) -> dict:
    """
    URLをクロールしてページ情報を返す（fetch → parse を一括で行う）。

    Args:
        url: クロール対象URL

    Returns:
        ページ情報の辞書。失敗時も crawl_status で判別できる
    """
    html = fetch_page(url)

    # HTML取得に失敗した場合
    if not html:
        return {
            "url"         : url,
            "crawl_status": "failed",
            "crawled_at"  : datetime.now().isoformat(),
        }

    try:
        return parse_html(html, url)
    except Exception as e:
        return {
            "url"         : url,
            "crawl_status": "error",
            "crawled_at"  : datetime.now().isoformat(),
        }
