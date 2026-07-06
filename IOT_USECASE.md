# IOT_USECASE

This document explains how to use `tool_genre: "iot"` tools from `uag`.

It is a common guide for IoT, LAN devices, BLE devices, and cloud-connected devices. It focuses on what to use first, in what order, and what to check when something fails.

## Purpose

- List devices on the LAN or nearby over BLE
- Read device status
- Control devices when needed
- Subscribe to state changes and receive automatic LLM notifications
- Prefer machine-friendly JSON output
- Understand failure reasons quickly and move to the next check

## Tool groups

The main `tool_genre: "iot"` tools are:

### BLE

- `ble_ops`
- `switchbot_ble_scan`
- `switchbot_ble_status`
- `switchbot_ble_control`

### SwitchBot Cloud

- `switchbot_cloud_list`
- `switchbot_cloud_status`
- `switchbot_cloud_control`
- `switchbot_batch`
- `switchbot_subscribe` (new)
- `switchbot_unsubscribe` (new)

### ECHONET Lite

- `echonet_scan`
- `echonet_node_status`
- `echonet_object_list`
- `echonet_property_list`
- `echonet_property_get`
- `echonet_property_set`
- `echonet_control`
- `echonet_monitor`
- `echonet_cache`
- `echonet_subscribe` (new)
- `echonet_unsubscribe` (new)

### BACnet

- `bacnet_scan`
- `bacnet_read`
- `bacnet_write`
- `bacnet_cov_subscribe`
- `bacnet_cov_unsubscribe`

### UPnP

- `upnp_scan`
- `upnp_igd_control`

### Matter

Use Matter tools for Matter-connected devices.

Best for:

- Inspecting controller / bridge / device structure
- Listing controllers and bridges
- Checking device status
- Inspecting endpoints and clusters
- Subscribing to attribute changes

Notes:

- Matter keeps controller / bridge / device separate
- `matter_subscribe` / `matter_unsubscribe` / `matter_subscription_list` available for state monitoring
- The current implementation is read-only and uses local JSON files or environment variables
- `matter_endpoint_list` and `matter_cluster_list` are available for structure details
- Control is a future extension target

Typical flow:

1. Use `matter_controller_list` to inspect controllers
2. Use `matter_bridge_list` to inspect bridges
3. Use `matter_device_status` to inspect the target device
4. Use `matter_endpoint_list` and `matter_cluster_list` if you need more structure

## Practical usage flow

### A. You want to see what is available

Start with discovery or listing tools.

- BLE: `ble_ops` / `switchbot_ble_scan`
- ECHONET Lite: `echonet_scan`
- BACnet: `bacnet_scan`
- UPnP: `upnp_scan`
- Matter: `matter_controller_list` / `matter_bridge_list`
- SwitchBot Cloud: `switchbot_cloud_list`

### B. You want to check the current state

After listing, use status tools.

- BLE: `switchbot_ble_status`
- SwitchBot Cloud: `switchbot_cloud_status`
- ECHONET Lite: `echonet_node_status`
- BACnet: `bacnet_read`
- Matter: `matter_device_status`

### C. You want more detail

Use the detail tools to inspect structure.

- ECHONET Lite: `echonet_object_list`, `echonet_property_list`, `echonet_property_get`
- BACnet: `bacnet_read` (any object/property)
- Matter: `matter_endpoint_list`, `matter_cluster_list`
- UPnP: check `upnp_igd_control` results

### D. You want to control something

Only do this when the target is clear and the action is supported.

- BLE: `switchbot_ble_control`
- SwitchBot Cloud: `switchbot_cloud_control` / `switchbot_batch`
- ECHONET Lite: `echonet_property_set`, `echonet_control`
- BACnet: `bacnet_write`
- UPnP: `upnp_igd_control`

Matter is currently mainly read-only.
Control is a future extension target.

### E. You want to be notified when something changes

Use subscription tools to receive push or polling notifications.

| Protocol | Mechanism | Subscribe | Unsubscribe | Notes |
|---|---|---|---|---|
| BACnet | COV (Change of Value) push | `bacnet_cov_subscribe` | `bacnet_cov_unsubscribe` | Device pushes changes automatically. Fastest. |
| Matter | Attribute Subscription | `matter_subscribe` | `matter_unsubscribe` | Device pushes attribute changes. |
| ECHONET Lite | INF notification (UDP multicast) | `echonet_subscribe` | `echonet_unsubscribe` | Device broadcasts unsolicited property changes. |
| SwitchBot Cloud | Polling (interval-based) | `switchbot_subscribe` | `switchbot_unsubscribe` | No webhook; polls at configurable interval (min 10s). |

All subscriptions queue events into the internal scheduler. When a change is detected,
the LLM receives an automatic prompt on the next turn.

Subscription example flow:

```
1. bacnet_cov_subscribe ip=192.168.1.101 object_type=analogInput object_instance=1 \
     label="3F会議室_室温" on_change_prompt="室温変化を報告"
   → task_id=1

2. (background) BACnet device sends COV when temperature changes
   → SchedulerStore queues event

3. (next LLM turn) LLM receives: "3F会議室_室温: presentValue changed to 26.5"

4. bacnet_cov_unsubscribe task_id=1  (when monitoring is no longer needed)
```

## `output_format` usage

### `json`

- Best for parsing and automation
- Best when passing output to other tools
- Best for logs and records

### `text`

- Best for quick visual checks
- Best when a human just wants to inspect the result
- Best when you want short error messages

Rule of thumb:

- Use `json` for scripts and automation
- Use `text` only for quick manual checks

## Tool notes

### `ble_ops`

- General BLE discovery and read/write
- Supports `scan`, `read`, and `write`
- Use `scan_mode` to choose BLE-only or Classic + BLE

Common uses:

- Find nearby devices
- Connect to a known address and read GATT values
- Write values to a characteristic

### `switchbot_ble_*`

- For SwitchBot BLE devices
- Use discovery, then status, then control

### `switchbot_cloud_*`

- For SwitchBot Cloud API
- Use list, status, then control
- Requires credentials (`UAGENT_SWITCHBOT_TOKEN`, `UAGENT_SWITCHBOT_SECRET`)
- Supports infrared remote devices (TV, air conditioner, light, etc.)
  - on/off/brightness_up/brightness_down
  - Air conditioner supports mode/fan_speed parameters

### `switchbot_subscribe` / `switchbot_unsubscribe`

- Polling-based subscription since SwitchBot Cloud has no webhook
- Polls at configurable interval (default 60s, minimum 10s)
- On state change, queues LLM notification via SchedulerStore
- Use `switchbot_unsubscribe` to cancel or list active subscriptions

### `switchbot_batch`

- Execute multiple SwitchBot commands in a single call
- Each command uses `device_id` or `device_name` to identify the target
- Fetches the device list only once, making multi-step operations more efficient

### `echonet_*`

- For LAN ECHONET Lite devices
- Use discovery → status → detail → control → monitoring
- Pay attention to multicast and interface settings

### `echonet_subscribe` / `echonet_unsubscribe`

- Listens for ECHONET Lite INF (notification, ESV=0x73) multicast frames
- Filters by source IP and optional EOJ code
- No polling required; device broadcasts changes unsolicited
- Background UDP multicast listener thread (started on first subscribe)
- Use `echonet_unsubscribe` to cancel or list active subscriptions

### `bacnet_*`

- For BACnet/IP devices on the local network
- Requires BAC0 library (auto-installed on first use)
- BACnet objects: analogInput/BinaryOutput/AnalogValue etc.
- Use `bacnet_read` for sensors (temperature, humidity, power)
- Use `bacnet_write` for control (setpoint, on/off)

### `bacnet_cov_subscribe` / `bacnet_cov_unsubscribe`

- Uses BAC0.lite COV subscription for push notifications
- Requires background asyncio event loop (started on first subscribe)
- Supports per-object subscription with label and custom LLM prompt
- BAC0 automatically renews subscription before lifetime expiry (default 900s)
- Use `bacnet_cov_unsubscribe` to cancel or list active subscriptions

### `upnp_*`

- For UPnP / SSDP devices
- Discover first, then handle IGD
- Depends on router UPnP settings

### `matter_*`

- Handle Matter controller / bridge / device separately
- Start with list, then status, then endpoint / cluster if needed
- `matter_subscribe` for attribute change monitoring
- Mainly read-only at present

## Common failure patterns

### 1. Not found

- `not_found`
- The target ID is wrong
- The device is not visible on the network

### 2. Ambiguous

- `ambiguous_target`
- `device_id` alone is not enough
- You may need `controller_id`, `bridge_id`, or `endpoint`

### 3. Configuration missing

- `config_missing`
- Authentication is missing
- Environment variables are not set

### 4. Communication failure

- `network_error`
- `timeout`
- BLE permission issues
- Multicast or UDP blocked
- BAC0 library not installed (auto-install may fail behind proxy)

### 5. Unsupported

- `unsupported_device`
- `unsupported_property`
- The device or feature is not supported yet

## Operational notes

- Do not control a target while it is still ambiguous
- Always insert list/status checks before control
- If something fails, check the target ID, interface, credentials, and network separately
- Do not keep secrets in logs
- `text` is readable, but keep `json` if you may process the output later
- Subscriptions only live while uag is running (no persistence across restarts)
- Multiple subscriptions to the same device are allowed

## Environment variables

### SwitchBot

- `UAGENT_SWITCHBOT_TOKEN`
- `UAGENT_SWITCHBOT_SECRET`

### Matter

- If you need stored connection or target data, use the `UAGENT_MATTER_...` prefix

### ECHONET Lite / UPnP / BACnet

- Use the `UAGENT_` prefix when environment variables are needed
- Do not output secrets in logs
