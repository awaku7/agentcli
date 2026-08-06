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

### MQTT

- `mqtt_publish`
- `mqtt_subscribe`
- `mqtt_unsubscribe`

Best for:

- Pub/sub messaging with IoT/BEMS devices
- Sensor data streaming
- Cloud platform integration (AWS IoT, Azure IoT Hub)
- Requires an MQTT broker (Mosquitto, EMQX, etc.)

### DALI

- `dali_scan`
- `dali_read`
- `dali_write`

Best for:

- Lighting control (on/off, dimming 0-254)
- DALI USB adapters (Tridonic, Hasseb) or TCP server (daliserver)
- Single device, group (0-15), or broadcast addressing

Notes:

- Addresses 0-63, groups 0-15
- Requires DALI USB adapter or daliserver running on the network
- python-dali library (auto-installed)
- `dali_read` queries status, actual/min/max/power-on levels

### OPC UA

- `opcua_scan`
- `opcua_browse`
- `opcua_read`
- `opcua_write`
- `opcua_subscribe`
- `opcua_unsubscribe`

Best for:

- Industrial automation and SCADA integration
- Reading/writing variable values via NodeId
- Subscribing to data changes (push notifications)
- Browsing server address space

### UPnP

- `upnp_scan`
- `upnp_igd_control`

### Modbus TCP

- `modbus_scan`
- `modbus_read`
- `modbus_write`
- `modbus_monitor`

Best for:

- Reading sensors and meters (input registers, holding registers)
- Controlling actuators (coils, holding registers)
- Periodic polling with change detection

Notes:

- Modbus has no built-in discovery; `modbus_scan` probes IP ranges and unit IDs
- Default port: 502
- Unit ID range: 1-247

### Matter

Use Matter tools for Matter-connected devices.

Best for:

- Inspecting controller / bridge / device structure
- Listing controllers and bridges
- Checking device status
- Controlling devices (on/off, open/close, set_value, lock/unlock)
- Inspecting endpoints and clusters
- Subscribing to attribute changes

Notes:

- Matter keeps controller / bridge / device separate
- `matter_control` supports on/off, open/close, set_value, lock/unlock
- Control commands are queued to `UAGENT_MATTER_COMMAND_JSON` env var or `UAGENT_MATTER_COMMAND_FILE`
- An external handler reads the queue and executes the command on the Matter fabric
- `matter_subscribe` / `matter_unsubscribe` / `matter_subscription_list` available for state monitoring
- Configuration uses local JSON files or environment variables
- `matter_endpoint_list` and `matter_cluster_list` are available for structure details

Typical flow:

1. Use `matter_controller_list` to inspect controllers
1. Use `matter_bridge_list` to inspect bridges
1. Use `matter_device_status` to inspect the target device
1. Use `matter_endpoint_list` and `matter_cluster_list` if you need more structure
1. Use `matter_control` to send control commands

## Practical usage flow

### A. You want to see what is available

Start with discovery or listing tools.

- BLE: `ble_ops` / `switchbot_ble_scan`
- ECHONET Lite: `echonet_scan`
- BACnet: `bacnet_scan`
- DALI: `dali_scan`
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
- DALI: `dali_write`
- MQTT: `mqtt_publish`
- Matter: `matter_control`
- Modbus: `modbus_write`
- OPC UA: `opcua_write`
- UPnP: `upnp_igd_control`

Matter control is supported via command queuing. Commands are queued to
`UAGENT_MATTER_COMMAND_JSON` or `UAGENT_MATTER_COMMAND_FILE` for external processing.

### E. You want to be notified when something changes

Use subscription tools to receive push or polling notifications.

| Protocol | Mechanism | Subscribe | Unsubscribe | Notes |
|---|---|---|---|---|
| BACnet | COV (Change of Value) push | `bacnet_cov_subscribe` | `bacnet_cov_unsubscribe` | Device pushes changes automatically. Fastest. |
| Matter | Attribute Subscription | `matter_subscribe` | `matter_unsubscribe` | Device pushes attribute changes. |
| ECHONET Lite | INF notification (UDP multicast) | `echonet_subscribe` | `echonet_unsubscribe` | Device broadcasts unsolicited property changes. |
| MQTT | Message subscription | `mqtt_subscribe` | `mqtt_unsubscribe` | Pub/sub messaging. Wildcard topics supported. |
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
- Scan results display EOJ (Enhanced Object) class names localized to 34 languages
  - Japanese locale: native Japanese class names (e.g., `家庭用エアコン`, `電動ブラインド・日よけ`)
  - Other locales: translated names via tool JSON (e.g., `Home air conditioner`/`Klimaanlage`/`家用空调`)
  - Fallback to English name if translation is unavailable
  - JSON file: `echonet_scan_tool.json` (32 language entries for 55 EOJ classes)

### `echonet_subscribe` / `echonet_unsubscribe`

- Listens for ECHONET Lite INF (notification, ESV=0x73) multicast frames
- Filters by source IP and optional EOJ code
- No polling required; device broadcasts changes unsolicited
- Background UDP multicast listener thread (started on first subscribe)
- Use `echonet_unsubscribe` to cancel or list active subscriptions

### `mqtt_*`

- Publish/subscribe messaging protocol for IoT/BEMS
- Requires an MQTT broker (Mosquitto, EMQX, HiveMQ, AWS IoT Core, etc.)
- `mqtt_publish`: connect, send a message, disconnect (one-shot)
- `mqtt_subscribe`: persistent subscription with background message handling
  - Messages are forwarded to SchedulerStore and automatically delivered to the LLM
- TLS (MQTTS) supported via `use_tls=true` (default port: 8883)
- `insecure=true` disables certificate verification for self-signed certs
- Wildcard topics supported: `building/+/temperature`, `#`
- QoS levels: 0 (fire-and-forget), 1 (at least once), 2 (exactly once)

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

### `dali_*`

- DALI lighting control (IEC 62386)
- Addresses 0-63, groups 0-15, broadcast
- `dali_scan`: probe all 64 addresses, return responsive devices
- `dali_read`: query status, actual/min/max/power-on levels
- `dali_write`: on/off/dim (0-254) control
- Driver types: tridonic (USB), hasseb (USB), daliserver (TCP), lunatone (RS232), atxled (HAT)
- `daliserver` driver connects to https://github.com/onitake/daliserver over TCP (port 55825)

### `matter_*`

- Handle Matter controller / bridge / device separately
- Start with list, then status, then endpoint / cluster if needed
- `matter_control` for control commands (on/off, open/close, lock/unlock, set_value)
- `matter_subscribe` for attribute change monitoring
- Control commands are queued to `UAGENT_MATTER_COMMAND_JSON` or `UAGENT_MATTER_COMMAND_FILE` for external execution

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
