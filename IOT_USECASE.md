# IOT_USECASE

This document explains how to use `tool_genre: "iot"` tools from `uag`.

It is a common guide for IoT, LAN devices, BLE devices, and cloud-connected devices. It focuses on what to use first, in what order, and what to check when something fails.

## Purpose

- List devices on the LAN or nearby over BLE
- Read device status
- Control devices when needed
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

### UPnP

- `upnp_scan`
- `upnp_igd_control`

### MatterUse Matter tools for Matter-connected devices.

Best for:

- Inspecting controller / bridge / device structure
- Listing controllers and bridges
- Checking device status
- Inspecting endpoints and clusters

Notes:

- Matter keeps controller / bridge / device separate
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
- UPnP: `upnp_scan`
- Matter: `matter_controller_list` / `matter_bridge_list`
- SwitchBot Cloud: `switchbot_cloud_list`

### B. You want to check the current state

After listing, use status tools.

- BLE: `switchbot_ble_status`
- SwitchBot Cloud: `switchbot_cloud_status`
- ECHONET Lite: `echonet_node_status`
- Matter: `matter_device_status`

### C. You want more detail

Use the detail tools to inspect structure.

- ECHONET Lite: `echonet_object_list`, `echonet_property_list`, `echonet_property_get`
- Matter: `matter_endpoint_list`, `matter_cluster_list`
- UPnP: check `upnp_igd_control` results

### D. You want to control something

Only do this when the target is clear and the action is supported.

- BLE: `switchbot_ble_control`
- SwitchBot Cloud: `switchbot_cloud_control` / `switchbot_batch`
- ECHONET Lite: `echonet_property_set`, `echonet_control`
- UPnP: `upnp_igd_control`

Matter is currently mainly read-only.
Control is a future extension target.

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
- Requires credentials
- Supports infrared remote devices (TV, air conditioner, light, etc.)
  - on/off/brightness_up/brightness_down
  - Air conditioner supports mode/fan_speed parameters

### `switchbot_batch`

- Execute multiple SwitchBot commands in a single call
- Each command uses `device_id` or `device_name` to identify the target
- Fetches the device list only once, making multi-step operations more efficient

### `echonet_*`

- For LAN ECHONET Lite devices
- Use discovery → status → detail → control → monitoring
- Pay attention to multicast and interface settings

### `upnp_*`

- For UPnP / SSDP devices
- Discover first, then handle IGD
- Depends on router UPnP settings

### `matter_*`

- Handle Matter controller / bridge / device separately
- Start with list, then status, then endpoint / cluster if needed
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

## Environment variables

### SwitchBot

- `UAGENT_SWITCHBOT_TOKEN`
- `UAGENT_SWITCHBOT_SECRET`

### Matter

- If you need stored connection or target data, use the `UAGENT_MATTER_...` prefix

### ECHONET Lite / UPnP

- Use the `UAGENT_` prefix when environment variables are needed
- Do not output secrets in logs
