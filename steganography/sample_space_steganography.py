"""全角ではなく、通常スペースと NO-BREAK SPACE でビットを表すサンプル。

0 = U+0020 (通常のスペース)
1 = U+00A0 (NO-BREAK SPACE)

注意: コピー、HTML変換、Unicode正規化などで壊れる可能性があります。
"""

from __future__ import annotations

import sys

NORMAL_SPACE = "\u0020"
NO_BREAK_SPACE = "\u00a0"


def text_to_bits(value: str) -> str:
    """文字列をUTF-8バイト列として、8ビット単位の文字列に変換する。"""
    return "".join(f"{byte:08b}" for byte in value.encode("utf-8"))


def bits_to_text(bits: str) -> str:
    """8ビット単位のビット列をUTF-8文字列に戻す。"""
    if len(bits) % 8 != 0:
        raise ValueError("ビット数は8の倍数である必要があります")
    if any(bit not in "01" for bit in bits):
        raise ValueError("ビット列には0と1だけを指定してください")

    data = bytes(int(bits[index : index + 8], 2) for index in range(0, len(bits), 8))
    return data.decode("utf-8")


def embed_bits(carrier: str, bits: str) -> str:
    """carrier中の通常スペースを、bitsに従って置き換える。"""
    if any(bit not in "01" for bit in bits):
        raise ValueError("ビット列には0と1だけを指定してください")

    space_count = carrier.count(NORMAL_SPACE)
    if space_count < len(bits):
        raise ValueError(
            f"スペースが不足しています: 必要={len(bits)}, 使用可能={space_count}"
        )

    result: list[str] = []
    bit_index = 0

    for char in carrier:
        if char == NORMAL_SPACE and bit_index < len(bits):
            result.append(NO_BREAK_SPACE if bits[bit_index] == "1" else NORMAL_SPACE)
            bit_index += 1
        else:
            result.append(char)

    return "".join(result)


def extract_bits(encoded: str, bit_count: int | None = None) -> str:
    """encoded中の通常スペース/NBSPからビット列を取り出す。"""
    bits = "".join(
        "0" if char == NORMAL_SPACE else "1"
        for char in encoded
        if char in (NORMAL_SPACE, NO_BREAK_SPACE)
    )

    if bit_count is not None:
        if len(bits) < bit_count:
            raise ValueError(
                f"ビットが不足しています: 必要={bit_count}, 取得可能={len(bits)}"
            )
        bits = bits[:bit_count]

    return bits


def embed_text(carrier: str, hidden_text: str) -> str:
    """hidden_textをUTF-8ビット列にしてcarrierへ埋め込む。"""
    return embed_bits(carrier, text_to_bits(hidden_text))


def embed_repeating_text(carrier: str, hidden_text: str) -> str:
    """スペースが余る場合、hidden_textのビット列を繰り返して埋め込む。"""
    bits = text_to_bits(hidden_text)
    if not bits:
        raise ValueError("hidden_text は空にできません")

    result = []
    bit_index = 0
    for char in carrier:
        if char == NORMAL_SPACE:
            result.append(
                NO_BREAK_SPACE if bits[bit_index % len(bits)] == "1" else NORMAL_SPACE
            )
            bit_index += 1
        else:
            result.append(char)
    return "".join(result)


def extract_text(encoded: str, byte_length: int) -> str:
    """encodedから指定バイト数の隠し文字列を取り出す。"""
    bits = extract_bits(encoded, bit_count=byte_length * 8)
    return bits_to_text(bits)


def main() -> None:
    # Windowsのcp932コンソールでもNBSPを出力できるようにする。
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    # 24個以上のスペースが必要。ここでは "SBC" (3バイト=24ビット) を埋め込む。
    carrier = (
        "This is a sample sentence with enough spaces to carry "
        "a small hidden message for testing in this example. "
        "Please keep the spaces unchanged when copying this text."
    )
    hidden = "SBC"

    encoded = embed_repeating_text(carrier, hidden)

    print("元の文章:")
    print(carrier)
    print()
    print("埋め込み後の文章:")
    print(encoded)
    print()
    print("repr()で確認（NBSPは\\xa0として見える）:")
    print(repr(encoded))
    print()
    print("埋め込みビット列:")
    print(extract_bits(encoded, bit_count=len(hidden.encode("utf-8")) * 8))
    print()
    print("復元結果:")
    print(extract_text(encoded, byte_length=len(hidden.encode("utf-8"))))


if __name__ == "__main__":
    main()
