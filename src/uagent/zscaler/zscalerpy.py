import socket
from OpenSSL import SSL, crypto
import certifi
import hashlib
import os
import shutil
import tempfile
from datetime import datetime

# certifi のバンドルを直接更新する（更新は破壊的になり得るため、必ずバックアップを作成する）
CACERT_PATH = certifi.where()
TARGET_HOST = "www.google.co.jp"  # 任意のHTTPSサイト（Zscaler経由想定）

# 自己署名ルートも追加対象に含める（Zscaler Root 等のケースを想定）
INCLUDE_SELF_SIGNED_ROOT = True


def get_cert_chain(hostname, port=443):
    print(
        f"[INFO] Connecting to {hostname}:{port} to retrieve full certificate chain..."
    )
    ctx = SSL.Context(SSL.TLS_CLIENT_METHOD)

    # MITM（Zscaler 等）経由のチェーン取得を目的として検証を無効化している
    ctx.set_verify(SSL.VERIFY_NONE, lambda *x: True)

    sock = socket.create_connection((hostname, port))
    ssl_conn = SSL.Connection(ctx, sock)
    ssl_conn.set_connect_state()
    ssl_conn.set_tlsext_host_name(hostname.encode())
    ssl_conn.do_handshake()

    certs = ssl_conn.get_peer_cert_chain()
    ssl_conn.close()
    sock.close()
    print(f"[INFO] Retrieved {len(certs)} certificates from server.")
    return certs


def get_fingerprint(cert):
    der = crypto.dump_certificate(crypto.FILETYPE_ASN1, cert)
    return hashlib.sha256(der).hexdigest()


def dn_str(x509name: crypto.X509Name) -> str:
    # 参考用：安定化のため並び順を固定し、大小文字をそのまま維持
    # 注意: 同一属性が複数あるDNでは情報が欠落し得るため、同一性判定には使わない。
    comps = {k.decode(): v.decode() for k, v in x509name.get_components()}
    keys = ["C", "ST", "L", "O", "OU", "CN", "emailAddress", "serialNumber"]
    return ",".join(f"{k}={comps[k]}" for k in keys if k in comps)


def is_self_signed(cert: crypto.X509) -> bool:
    # subject==issuer を自己署名の目安として扱う
    return dn_str(cert.get_subject()) == dn_str(cert.get_issuer())


def is_ca_certificate(cert: crypto.X509) -> bool:
    """BasicConstraints を確認して CA 証明書か判定する。拡張が無い/読めない場合は False。"""
    try:
        for i in range(cert.get_extension_count()):
            ext = cert.get_extension(i)
            if ext.get_short_name() == b"basicConstraints":
                # 例: 'CA:TRUE' / 'CA:TRUE, pathlen:0'
                val = str(ext)
                return "CA:TRUE" in val
    except Exception:
        return False
    return False


def get_cert_blocks(pem_text: str):
    # 既存の cacert.pem から PEM ブロック（BEGIN〜END）を抽出
    blocks = []
    start = "-----BEGIN CERTIFICATE-----"
    end = "-----END CERTIFICATE-----"
    pos = 0
    while True:
        i = pem_text.find(start, pos)
        if i < 0:
            break
        j = pem_text.find(end, i)
        if j < 0:
            break
        block = pem_text[i : j + len(end)]
        blocks.append(block.strip() + "\n")
        pos = j + len(end)
    return blocks


def load_x509_from_pem_block(block: str) -> crypto.X509:
    return crypto.load_certificate(crypto.FILETYPE_PEM, block.encode("utf-8"))


def update_cacert_with_intermediates(chain_certs, cacert_path):
    print(f"[INFO] Updating cacert.pem at {cacert_path}...")
    with open(cacert_path, "r", encoding="utf-8") as f:
        existing_text = f.read()

    existing_blocks = get_cert_blocks(existing_text)

    fp_to_index = {}
    for idx, blk in enumerate(existing_blocks):
        try:
            x = load_x509_from_pem_block(blk)
            fp = get_fingerprint(x)
            fp_to_index.setdefault(fp, idx)
        except Exception as e:
            print(f"[WARN] Skipping unparsable block at index {idx}: {e}")

    updated_blocks = list(existing_blocks)
    added = 0

    for cert in chain_certs:
        # CA証明書のみ追加対象にする（leaf を混入させない）
        if not is_ca_certificate(cert):
            print("[INFO] CA証明書ではないためスキップ")
            continue

        # 自己署名ルートも追加対象に含める（要望により）
        if (not INCLUDE_SELF_SIGNED_ROOT) and is_self_signed(cert):
            print("[INFO] 自己署名（ルート）扱いのためスキップ")
            continue

        new_fp = get_fingerprint(cert)
        new_pem = (
            crypto.dump_certificate(crypto.FILETYPE_PEM, cert).decode("utf-8").strip()
            + "\n"
        )

        if new_fp in fp_to_index:
            print(f"[INFO] 同一証明書（fp={new_fp[:16]}...）は既に存在。スキップ。")
            continue

        print(f"[INFO] 新規CA証明書を追加（fp={new_fp[:16]}...）。")
        updated_blocks.append(new_pem)
        added += 1
        fp_to_index[new_fp] = len(updated_blocks) - 1

    if added == 0:
        print("[INFO] 追加すべき証明書はありませんでした。")
        return

    # バックアップ作成（毎回・コピー）
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{cacert_path}.{ts}.bak"
    shutil.copy2(cacert_path, backup_path)
    print(f"[INFO] 元の cacert.pem をバックアップ: {backup_path}")

    # 一時ファイルに書き込み→置換（失敗時に元を残す）
    tmp_dir = os.path.dirname(cacert_path) or "."
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        newline="\n",
        delete=False,
        dir=tmp_dir,
        prefix="cacert.",
        suffix=".tmp",
    ) as tf:
        tf.write("\n".join(b.strip() for b in updated_blocks) + "\n")
        tmp_path = tf.name

    os.replace(tmp_path, cacert_path)
    print(f"[INFO] cacert.pem を更新しました（追加 {added}）")


def main():
    certs = get_cert_chain(TARGET_HOST)
    if len(certs) <= 1:
        print("[INFO] 中間証明書がありません（1枚のみ）")
        return

    # leaf を除いたチェーン要素を候補として渡し、関数内で CA 判定フィルタする
    candidates = certs[1:]
    update_cacert_with_intermediates(candidates, CACERT_PATH)


if __name__ == "__main__":
    main()
