"""通常スペース/U+00A0を使った簡易ステガノグラフィー検出器。"""

from __future__ import annotations

import argparse
from pathlib import Path

NORMAL_SPACE = "\u0020"  # 0
NO_BREAK_SPACE = "\u00A0"  # 1


def extract_bits(text: str) -> str:
    """文章中の通常スペースとNBSPからビット列を抽出する。"""
    bits = []
    for char in text:
        if char == NORMAL_SPACE:
            bits.append("0")
        elif char == NO_BREAK_SPACE:
            bits.append("1")
    return "".join(bits)


def bits_to_bytes(bits: str) -> bytes:
    """ビット列をバイト列に変換する。"""
    if len(bits) % 8 != 0:
        raise ValueError("ビット数が8の倍数ではありません")
    if any(bit not in "01" for bit in bits):
        raise ValueError("ビット列には0と1だけを指定してください")
    return bytes(
        int(bits[index : index + 8], 2)
        for index in range(0, len(bits), 8)
    )


def decode_repeated_bits(bits: str, byte_length: int) -> str:
    """繰り返し埋め込まれたビット列を、完全な単位ごとに復元する。"""
    unit_bits = byte_length * 8
    complete_bits = bits[: len(bits) - (len(bits) % unit_bits)]
    if not complete_bits:
        raise ValueError("完全なメッセージ単位がありません")
    messages = [
        bits_to_bytes(complete_bits[index : index + unit_bits]).decode("utf-8")
        for index in range(0, len(complete_bits), unit_bits)
    ]
    return " | ".join(messages)


def detect(path: Path, byte_length: int) -> str:
    """ファイルから指定バイト数の隠しメッセージを復元する。"""
    text = path.read_text(encoding="utf-8")
    bits = extract_bits(text)
    required_bits = byte_length * 8

    if len(bits) < required_bits:
        raise ValueError(
            f"検出可能なビットが不足しています: "
            f"必要={required_bits}, 検出={len(bits)}"
        )

    payload = bits_to_bytes(bits[:required_bits])
    return payload.decode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="通常スペース/U+00A0から隠し文字列を検出します"
    )
    parser.add_argument("path", type=Path, help="検査するUTF-8テキストファイル")
    parser.add_argument(
        "--bytes",
        type=int,
        default=3,
        dest="byte_length",
        help="復元するバイト数（既定: 3。SBCなら3）",
    )
    args = parser.parse_args()

    text = args.path.read_text(encoding="utf-8")
    bits = extract_bits(text)

    print(f"ファイル: {args.path}")
    print(f"空白ビット数: {len(bits)}")
    print(f"U+0020 (0) の数: {bits.count('0')}")
    print(f"U+00A0 (1) の数: {bits.count('1')}")
    print(f"抽出ビット列: {bits}")

    try:
        print(f"繰り返し復元: {decode_repeated_bits(bits, args.byte_length)}")
    except (UnicodeDecodeError, ValueError) as error:
        print(f"繰り返し復元失敗: {error}")

    try:
        message = detect(args.path, args.byte_length)
    except (UnicodeDecodeError, ValueError) as error:
        print(f"復元失敗: {error}")
        raise SystemExit(1) from error

    print(f"復元メッセージ: {message}")


if __name__ == "__main__":
    main()
