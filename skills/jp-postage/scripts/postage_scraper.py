#!/usr/bin/env python3
"""
JP Postage Scraper
日本郵便の公式サイトから郵便料金をスクレイピングして表示する。
"""
import asyncio
import sys
from typing import Any

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

TARGET_URL = "https://www.post.japanpost.jp/service/send/domestic/mail/letter/"


async def fetch_page_html(url: str) -> str:
    """Playwright でページを開き、レンダリング後の HTML を取得する。"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url, wait_until="networkidle", timeout=30000)
        html = await page.content()
        await browser.close()
        return html


def extract_postage(html: str) -> dict[str, Any]:
    """HTML の table 要素から郵便料金データを抽出する。"""
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")
    result: dict[str, Any] = {
        "source_url": TARGET_URL,
        "postage": {},
    }

    if len(tables) < 7:
        # fallback: テキストベース抽出
        text = soup.get_text(separator="\n", strip=True)
        lines = text.split("\n")
        for i, line in enumerate(lines):
            if "更新" in line and "年" in line and "月" in line:
                result["updated"] = line.strip()
                break
        return result

    # Table 1: 定形郵便物 (50g以内 → 110円)
    t1 = tables[1]
    rows = t1.find_all("tr")
    for row in rows:
        cells = row.find_all("td")
        if len(cells) >= 3:
            weight = cells[1].get_text(strip=True)
            price = cells[2].get_text(strip=True)
            result["postage"]["定形郵便物"] = {"weight": weight, "price": price}
            break

    # Table 2: 定形外郵便物 (規格内 / 規格外)
    t2 = tables[2]
    rows = t2.find_all("tr")
    standard_inner: list[dict[str, str]] = []
    standard_outer: list[dict[str, str]] = []
    for row in rows:
        cells = row.find_all("td")
        if len(cells) >= 3:
            weight = cells[0].get_text(strip=True)
            inner_price = cells[1].get_text(strip=True)
            outer_price = cells[2].get_text(strip=True)
            if "取り扱いません" not in inner_price:
                standard_inner.append({"weight": weight, "price": inner_price})
            if "取り扱いません" not in outer_price:
                standard_outer.append({"weight": weight, "price": outer_price})

    if standard_inner:
        result["postage"]["定形外（規格内）"] = standard_inner
    if standard_outer:
        result["postage"]["定形外（規格外）"] = standard_outer

    # Table 3: ミニレター (25g以内 → 85円)
    t3 = tables[3]
    rows = t3.find_all("tr")
    for row in rows:
        cells = row.find_all("td")
        if len(cells) >= 3:
            weight = cells[1].get_text(strip=True)
            price = cells[2].get_text(strip=True)
            result["postage"]["ミニレター"] = {"weight": weight, "price": price}
            break

    # Table 4: レターパックライト (4kg以内 → 430円)
    t4 = tables[4]
    rows = t4.find_all("tr")
    for row in rows:
        cells = row.find_all("td")
        if len(cells) >= 3:
            weight = cells[1].get_text(strip=True)
            price = cells[2].get_text(strip=True)
            result["postage"]["レターパックライト"] = {"weight": weight, "price": price, "size": "A4, 厚さ3cm以内"}
            break

    # Table 5: レターパックプラス (4kg以内 → 600円)
    t5 = tables[5]
    rows = t5.find_all("tr")
    for row in rows:
        cells = row.find_all("td")
        if len(cells) >= 3:
            weight = cells[1].get_text(strip=True)
            price = cells[2].get_text(strip=True)
            result["postage"]["レターパックプラス"] = {"weight": weight, "price": price, "size": "A4, 厚さ制限なし"}
            break

    # Table 6: スマートレター (1kg以内 → 210円)
    t6 = tables[6]
    rows = t6.find_all("tr")
    for row in rows:
        cells = row.find_all("td")
        if len(cells) >= 3:
            weight = cells[1].get_text(strip=True)
            price = cells[2].get_text(strip=True)
            result["postage"]["スマートレター"] = {"weight": weight, "price": price, "size": "A5, 厚さ2cm以内"}
            break

    # 更新日
    text = soup.get_text(separator="\n", strip=True)
    for line in text.split("\n"):
        if "更新" in line and "年" in line and "月" in line:
            result["updated"] = line.strip()
            break

    return result


def format_markdown(data: dict[str, Any]) -> str:
    """抽出データを Markdown 表に整形する。"""
    lines = ["# 日本郵便 郵便料金一覧", ""]
    lines.append(f"出典: {data['source_url']}")
    if data.get("updated"):
        lines.append(f"更新日: {data['updated']}")
    lines.append("")

    postage = data.get("postage", {})

    if "定形郵便物" in postage:
        lines.append("## 定形郵便物（手紙・封書）")
        p = postage["定形郵便物"]
        lines.append(f"- 重量: {p['weight']} → **{p['price']}**")
        lines.append("")

    for cat in ["定形外（規格内）", "定形外（規格外）"]:
        if cat in postage:
            label = cat.replace("定形外（", "定形外郵便物（").replace("）", "）")
            lines.append(f"## {label}")
            lines.append("| 重量 | 料金 |")
            lines.append("|------|------|")
            for item in postage[cat]:
                lines.append(f"| {item['weight']} | **{item['price']}** |")
            lines.append("")

    specials = [
        ("ミニレター", "ミニレター（郵便書簡）"),
        ("スマートレター", "スマートレター"),
        ("レターパックライト", "レターパックライト"),
        ("レターパックプラス", "レターパックプラス"),
    ]
    has_specials = any(k in postage for k, _ in specials)
    if has_specials:
        lines.append("## その他サービス")
        lines.append("| 種類 | サイズ制限 | 重量 | 料金 |")
        lines.append("|------|-----------|------|------|")
        for k, label in specials:
            if k in postage:
                p = postage[k]
                size = p.get("size", "-")
                weight = p.get("weight", "-")
                price = p.get("price", "-")
                lines.append(f"| {label} | {size} | {weight} | **{price}** |")
        lines.append("")

    return "\n".join(lines)


async def main() -> None:
    try:
        html = await fetch_page_html(TARGET_URL)
        data = extract_postage(html)
        output = format_markdown(data)
        print(output)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
