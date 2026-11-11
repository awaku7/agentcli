
"""Compare nostr-sdk delivery using the recipient's NIP-17 relay list."""

import asyncio

import nostr_sdk as nostr

from uagent.nostr_remote_transport import fetch_nip17_relay_list


RECIPIENT_NPUB = (
    "npub1d0c9ehwjkn039salt09lqtdmrjxsls4cqgu0gcr3zklcztvqvm3stvjsf2"
)

UAG_RELAYS = [
    "wss://x.kojira.io",
    "wss://nos.lol",
    "wss://relay.snort.social",
]

MESSAGE = "SDK kind10050 direct test"


async def main():
    recipient = nostr.PublicKey.parse(RECIPIENT_NPUB)
    recipient_hex = recipient.to_hex()

    keys = nostr.Keys.generate()
    print("SDK送信者:", keys.public_key().to_bech32())

    print("\n[1] 0xChatのkind 10050を取得")

    try:
        inbox_relays = await fetch_nip17_relay_list(
            recipient_hex,
            UAG_RELAYS,
            allowed_relay_urls=UAG_RELAYS,
            timeout=8.0,
        )
    except Exception as exc:
        print("Relay一覧取得失敗:", type(exc).__name__, str(exc))
        return

    print("0xChatの受信Relay:")
    for relay in inbox_relays:
        print(" ", relay)

    # UAGと同じRelay許可リストを使用
    target_relays = [
        relay for relay in inbox_relays
        if relay in UAG_RELAYS
    ]

    print("\n[2] UAG設定との共通Relay:")
    for relay in target_relays:
        print(" ", relay)

    if not target_relays:
        print("共通Relayがありません。送信せず終了します。")
        return

    print("\n[3] nostr-sdkで送信")

    client = nostr.Client()

    try:
        for relay in target_relays:
            await client.add_relay(nostr.RelayUrl.parse(relay))

        await client.connect()

        event = nostr.nip17_make_private_msg(
            keys,
            recipient,
            MESSAGE,
        )

        print("Gift Wrap ID:", event.id().to_hex())
        result = await client.send_event(event)

        print("\nSDK送信結果:")
        print(result)

    except Exception as exc:
        print("SDK送信エラー:", type(exc).__name__, str(exc))
        raise

    finally:
        await client.shutdown()

    print("\n0xChatのメッセージリクエストも確認してください。")


if __name__ == "__main__":
    asyncio.run(main())
