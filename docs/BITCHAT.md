# pybitchat — BLE Mesh Communication

`pybitchat` enables peer-to-peer messaging over BLE Mesh, compatible with the [bitchat](https://bitchat.app) protocol. Messages are exchanged directly between nearby devices over Bluetooth Low Energy, and optionally relayed via Nostr for longer-distance communication.

> **Note**: Bitchat is a separate communication protocol managed by the bitchat project. uag integrates bitchat as a set of tool plugins — this page covers the uag-side usage.

## Tools

Two tool plugins provide the bitchat interface:

| Tool | Genre | Description |
|------|-------|-------------|
| `pybitchat_subscribe` | comm | Start/stop/monitor the BLE Mesh node. Chat mode for forwarding user input. |
| `pybitchat_send` | comm | Send text messages, announcements, or files over the mesh. |

## Quick Start

### 1. Start the node

```python
pybitchat_subscribe action="start" nickname="my-node"
```

This starts BLE advertising and scanning. The node appears as `my-node` to peers.
By default it uses the `mainnet` network. Use `network="testnet"` for testing.

**Status check**:
```python
pybitchat_subscribe action="status"
```

**Stop**:
```python
pybitchat_subscribe action="stop"
```

### 2. Send messages

Once the node is running:

```python
pybitchat_send type="text" payload="Hello from uag!"
```

This broadcasts to all nearby peers. To send to a specific peer:

```python
pybitchat_send type="text" payload="Hi!" recipient="<peer-id-hex>"
```

### 3. Send announcements

Announce your presence with a nickname:

```python
pybitchat_send type="announce" payload="my-node"
```

### 4. Enable chat mode

Chat mode forwards every user input to the mesh as a broadcast text message.
Messages received from the mesh are displayed in the terminal.

```python
pybitchat_subscribe action="chat_mode" on=true
```

To disable:
```python
pybitchat_subscribe action="chat_mode" on=false
```

### 5. Send files

```python
pybitchat_send type="file" payload="C:/path/to/file.pdf"
```

Files are encoded as TLV payload and transmitted to all connected peers.
Maximum file size: 1 MB.

## Nostr Transport

In addition to BLE, pybitchat can relay messages over Nostr relays for long-distance communication.

### Start with Nostr

```python
pybitchat_subscribe action="start" nickname="my-node" nostr=true
```

Optional: specify custom relays:
```python
pybitchat_subscribe action="start" nickname="my-node" nostr=true nostr_relays="relay1.com,relay2.com"
```

### Send via Nostr

By default, `pybitchat_send` uses BLE only. To send over Nostr:

```python
pybitchat_send type="text" payload="Hello Nostr!" via="nostr"
```

To send over both transports simultaneously:

```python
pybitchat_send type="text" payload="Hello world!" via="both"
```

### Nostr Pubkey

When Nostr transport is running, the node gets a keypair. Use the pubkey for targeted messaging:

```python
pybitchat_send type="text" payload="Direct message" recipient="<64-char-hex-pubkey>" via="nostr"
```

When recipient is a 64-character hex string, the message is encrypted using kind-1059 (NIP-17-compatible direct message).

## Geo Channels (Nostr only)

When Nostr transport is enabled, you can join geo-based channels using the `:bitchat geo` CLI commands.

### Join a geo channel

List available Geohash candidates in your area:
```
:bitchat geo join
```
This detects position via GPS sensor or IP geolocation and lists available geohash channels across precision levels (e.g. `#xn`, `#xn0m`, `#xn0m7`, `#mesh`).

Join a specific geohash channel:
```
:bitchat geo join xn0m7
```

Or specify coordinates manually:
```
:bitchat geo join 35.6762 139.6503 6
```

The command calculates a geohash and subscribes to Nostr messages from users in that area.

### Leave a geo channel

```
:bitchat geo leave xn76gg
```

### List active geo channels

```
:bitchat geo list
```

### Recommended precision values

| Precision | Approximate area |
|-----------|-----------------|
| 4 | ~39 km |
| 5 | ~4.9 km |
| 6 | ~1.2 km |
| 7 | ~152 m |
| 8 | ~38 m |

## CLI Commands (`:` short commands)

| Command | Description |
|---------|-------------|
| `:bitchat start [nickname] [--nostr] [--network <mainnet|testnet>]` | Start the BLE Mesh node |
| `:bitchat stop` | Stop the BLE Mesh node |
| `:bitchat on` | Enable chat mode (user input forwarded to mesh) |
| `:bitchat off` | Disable chat mode |
| `:bitchat status` | Show node state, chat mode, peers, Nostr status |
| `:bitchat peers` | List discovered Nostr bitchat peers |
| `:bitchat geo join [<geohash>|lat lng [prec]]` | List geo candidates or join a geohash channel |
| `:bitchat geo leave <geohash>` | Leave a geohash channel |
| `:bitchat geo list` | List active geo channels |
| `:nostr connect [relays]` | Connect to Nostr relays |
| `:nostr status` | Show Nostr status |
| `:nostr post <message>` | Post public text note (Kind 1) to Nostr |
| `:nostr timeline [limit]` | Fetch recent public notes from Nostr relays |
| `:nostr disconnect` | Disconnect from Nostr relays |

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  pybitchat_subscribe                 │
│  ┌─────────────────────┐  ┌──────────────────────┐  │
│  │    BLE Mesh (bleak) │  │  Nostr Transport     │  │
│  │  • advertise/scan   │  │  • relay messages    │  │
│  │  • fragmented send  │  │  • encrypted DMs     │  │
│  │  • message relay    │  │  • geo channels      │  │
│  └─────────┬───────────┘  └──────────┬───────────┘  │
│            │                         │              │
│            └──────────┬──────────────┘              │
│                       │                            │
│              ┌────────▼────────┐                    │
│              │  Outbound Queue │                    │
│              └────────┬────────┘                    │
│                       │                            │
│              ┌────────▼────────┐                    │
│              │  Chat Mode      │                    │
│              │  (input→mesh)   │                    │
│              └─────────────────┘                    │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│                  pybitchat_send                      │
│  Enqueue message → outbound queue → BLE / Nostr     │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│                  pybitchat_shared                     │
│  • Node identity (Noise X25519 + Ed25519 signing)   │
│  • BLE service (advertise/scan/connect)             │
│  • Fragment assembly                                │
│  • File transfer (TLV encoding)                     │
│  • Peer discovery & nickname tracking               │
│  • Auto-install dependencies (bleak, cryptography,  │
│    bitchat-protocol)                                │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│                  bitchat_noise                        │
│  Noise XX handshake (X25519 + ChaChaPoly + SHA256)  │
│  Wire-compatible with official bitchat app           │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│                  bitchat_geo                          │
│  GeoHash encoding/decoding                          │
│  Geo channel management (join/leave/list)           │
└─────────────────────────────────────────────────────┘
```

## Dependencies

Dependencies are auto-installed on first use:

| Package | Purpose |
|---------|---------|
| `bleak` | BLE (Bluetooth Low Energy) communication |
| `cryptography` | Noise XX handshake, encryption, key management |
| `bitchat-protocol` | Protocol definitions (packet encoding/decoding) |

## Wire Format

pybitchat is wire-compatible with the official bitchat app:

- **BLE**: Advertises service UUID `F47B5E2D-4A9E-4C5A-9B3F-8E1D2C3A4B5C` (mainnet) / `F47B5E2D-4A9E-4C5A-9B3F-8E1D2C3A4B5A` (testnet)
- **Protocol**: `Noise_XX_25519_ChaChaPoly_SHA256` handshake
- **Packet format**: BitchatPacket (version 1) with Ed25519 signatures
- **Fragmentation**: Automatic for payloads > 480 bytes
- **File transfer**: TLV-encoded (file name, size, MIME type, content)

## Security Notes

- Each node generates a fresh X25519 + Ed25519 keypair on first run.
- Direct messages use Noise XX handshake for end-to-end encryption.
- Messages are signed with Ed25519 for authenticity.
- The identity keypair is ephemeral (per process). No persistent key storage.
- Nostr messages to specific pubkeys use kind-1059 encrypted DMs.

## See also

- [COMMUNICATION.md](COMMUNICATION.md) — Other communication tools (Bluesky, Discord, Gmail, Teams)
- [IOT_USECASE.md](IOT_USECASE.md) — IoT device control tools
