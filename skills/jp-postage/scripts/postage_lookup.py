#!/usr/bin/env python3
"""
JP Postage Lookup - 郵便料金検索ツール
日本郵便の料金データ（2025年11月改訂版）を組み込みで保持
"""

import sys

POSTAGE_DATA = {
    "source": "data-print.jp (2025年11月改訂)",
    "updated": "2025-11-01",
    "domestic": {
        "first_class": {
            "name": "第一種郵便物（定形）",
            "description": "定形郵便物（長辺34cm以内、短辺25cm以内、厚さ1cm以内）",
            "rates": [{"weight": "50g以内", "price": 110}],
        },
        "first_class_nonstandard": {
            "name": "第一種郵便物（定形外）",
            "description": "定形外郵便物（規格内：長辺34cm以内、短辺25cm以内、厚さ3cm以内）",
            "rates": [
                {"weight": "50g以内", "standard": 140, "nonstandard": 260},
                {"weight": "100g以内", "standard": 180, "nonstandard": 290},
                {"weight": "150g以内", "standard": 270, "nonstandard": 390},
                {"weight": "250g以内", "standard": 320, "nonstandard": 450},
                {"weight": "500g以内", "standard": 510, "nonstandard": 660},
                {"weight": "1kg以内", "standard": 750, "nonstandard": 920},
                {"weight": "2kg以内", "standard": None, "nonstandard": 1350},
                {"weight": "4kg以内", "standard": None, "nonstandard": 1750},
            ],
        },
        "postcard": {
            "name": "第二種郵便物（はがき）",
            "rates": [
                {"type": "通常はがき", "price": 85},
                {"type": "往復はがき", "price": 170},
            ],
        },
        "fourth_class": {
            "name": "第四種郵便物（通信教育用）",
            "rates": [{"weight": "100gまで", "price": 15}],
        },
        "yuu_mail": {
            "name": "ゆうメール",
            "rates": [
                {"weight": "150g以内", "price": 190},
                {"weight": "250g以内", "price": 230},
                {"weight": "500g以内", "price": 320},
                {"weight": "1kg以内", "price": 380},
            ],
        },
        "option": {
            "express": {
                "name": "速達",
                "rates": [
                    {"weight": "250gまで", "price": 300},
                    {"weight": "1kgまで", "price": 400},
                    {"weight": "4kgまで", "price": 690},
                ],
            },
            "time_designated": {
                "name": "配達時間帯指定郵便",
                "rates": [
                    {"weight": "250gまで", "price": 440},
                    {"weight": "1kgまで", "price": 570},
                    {"weight": "4kgまで", "price": 920},
                ],
            },
            "registered": {
                "name": "書留",
                "rates": [
                    {"type": "簡易書留", "price": 350},
                    {"type": "一般書留（現金書留1万円まで）", "price": 480},
                    {"type": "引受時刻証明", "price": 350},
                    {"type": "配達証明（差出時）", "price": 350},
                    {"type": "配達証明（差出後）", "price": 480},
                ],
            },
        },
    },
}


def show_all():
    d = POSTAGE_DATA["domestic"]
    lines = [f"# 郵便料金一覧（{POSTAGE_DATA['updated']}）", ""]

    fc = d["first_class"]
    lines.append(f"## {fc['name']}")
    lines.append(f"- {fc['description']}")
    for r in fc["rates"]:
        lines.append(f"- {r['weight']}: **{r['price']}円**")
    lines.append("")

    fn = d["first_class_nonstandard"]
    lines.append(f"## {fn['name']}")
    lines.append(f"- {fn['description']}")
    lines.append("| 重量 | 規格内 | 規格外 |")
    lines.append("|------|--------|--------|")
    for r in fn["rates"]:
        s = f"{r['standard']}円" if r["standard"] else "-"
        ns = f"{r['nonstandard']}円" if r["nonstandard"] else "-"
        lines.append(f"| {r['weight']} | {s} | {ns} |")
    lines.append("")

    pc = d["postcard"]
    lines.append(f"## {pc['name']}")
    for r in pc["rates"]:
        lines.append(f"- {r['type']}: **{r['price']}円**")
    lines.append("")

    ym = d["yuu_mail"]
    lines.append(f"## {ym['name']}")
    lines.append("| 重量 | 料金 |")
    lines.append("|------|------|")
    for r in ym["rates"]:
        lines.append(f"| {r['weight']} | **{r['price']}円** |")
    lines.append("")

    op = d["option"]
    lines.append("## オプションサービス")
    for k, v in op.items():
        lines.append(f"### {v['name']}")
        for r in v["rates"]:
            t = r.get("type", r.get("weight", ""))
            lines.append(f"- {t}: **{r['price']}円**")

    print("\n".join(lines))


def search(query):
    q = query.lower()
    results = []
    d = POSTAGE_DATA["domestic"]

    if any(k in q for k in ["定形", "手紙", "封書", "ていけい"]):
        fc = d["first_class"]
        for r in fc["rates"]:
            results.append(f"定形郵便物 {r['weight']}: {r['price']}円")
        fn = d["first_class_nonstandard"]
        for r in fn["rates"]:
            if r["standard"]:
                results.append(f"定形外（規格内）{r['weight']}: {r['standard']}円")
            if r["nonstandard"]:
                results.append(f"定形外（規格外）{r['weight']}: {r['nonstandard']}円")

    if any(k in q for k in ["はがき", "ハガキ", "postcard"]):
        for r in d["postcard"]["rates"]:
            results.append(f"{r['type']}: {r['price']}円")

    if "ゆうメール" in q or "yu" in q:
        for r in d["yuu_mail"]["rates"]:
            results.append(f"ゆうメール {r['weight']}: {r['price']}円")

    if "速達" in q or "express" in q:
        for r in d["option"]["express"]["rates"]:
            results.append(f"速達 {r['weight']}: {r['price']}円")

    if "書留" in q or "registered" in q:
        for r in d["option"]["registered"]["rates"]:
            results.append(f"{r['type']}: {r['price']}円")

    if results:
        print(f"「{query}」の検索結果:")
        for r in results:
            print(f"  {r}")
    else:
        print(f"「{query}」に一致する料金情報は見つかりませんでした。")
        print("キーワード例: はがき, 定形, 定形外, ゆうメール, 速達, 書留")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        search(" ".join(sys.argv[1:]))
    else:
        show_all()
