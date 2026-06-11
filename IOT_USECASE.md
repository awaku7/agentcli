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

### Matter

- `matter_controller_list`
- `matter_bridge_list`
- `matter_device_status`
- `matter_endpoint_list`
- `matter_cluster_list`

## Common policy

### 1. Start with list/status tools

For IoT tools, it is important to identify the target correctly before trying control.

Basic flow:

1. Discover or list
2. Check status
3. Get details if needed
4. Control if needed

### 2. Use JSON by default

- Use `json` for automation and tool chaining
- Use `text` only for quick human checks
- When unsure, choose `json`

### 3. Make the target unambiguous

Control and detailed lookups can fail if the target is unclear.

Common identifiers:

- BLE: `address`, `char_uuid`
- SwitchBot: `device_id`, `device_name`
- ECHONET Lite: `ip_address`, `eoj`, `object_code`, `epc`
- UPnP: `interface`, `search_target`, `location`, `usn`
- Matter: `controller_id`, `bridge_id`, `device_id`, `endpoint`, `cluster`

### 4. Use null or omission for missing values

Keep the behavior consistent across tools.

- Use `null` for values that cannot be obtained
- Omit values that do not exist
- Avoid adding multiple keys with the same meaning

### 5. Keep failures short

Typical failure reasons:

- `config_missing`
- `not_found`
- `ambiguous_target`
- `network_error`
- `timeout`
- `unsupported_device`
- `invalid_argument`

### 6. Do not keep secrets

- Do not store tokens or secrets in logs or long-term memory
- If environment variables are used, standardize on the `UAGENT_` prefix

## How to use each group

### BLE

Use BLE for nearby Bluetooth Low Energy devices.

Best for:

- Discovering nearby devices
- Reading and writing GATT values
- SwitchBot BLE devices

Notes:

- Range and radio conditions matter
- Address handling differs slightly between Windows, Linux, and macOS
- Permissions or Bluetooth stack issues may cause failures

Typical flow:

1. Use `ble_ops` to discover devices
2. Use `switchbot_ble_status` to inspect the target
3. Use `switchbot_ble_control` to operate it

### SwitchBot Cloud

Use the cloud API to manage SwitchBot devices.

Best for:

- Listing devices in the account
- Checking device state
- Controlling devices remotely

Notes:

- Authentication is required
- Network access is usually more stable than local BLE
- Cloud API limits or response failures can still happen

Required credentials:

- `UAGENT_SWITCHBOT_TOKEN`
- `UAGENT_SWITCHBOT_SECRET`

Typical flow:

1. Use `switchbot_cloud_list` to inspect devices
2. Use `switchbot_cloud_status` to check the target
3. Use `switchbot_cloud_control` to operate it

### ECHONET Lite

Use ECHONET Lite for devices on the LAN.

Best for:

- Discovering home appliance nodes
- Reading node and object status
- Reading and writing EPC values
- Tracking changes with monitoring

Notes:

- Discovery may fail if multicast does not pass through
- Router or OS network settings can affect results
- `ip_address` and `interface` can be important

Typical flow:

1. Use `echonet_scan` to find nodes on the LAN
2. Use `echonet_node_status` to inspect the node
3. Use `echonet_object_list`, `echonet_property_list`, and `echonet_property_get` for details
4. Use `echonet_property_set` and `echonet_control` for control
5. Use `echonet_monitor` to track changes
6. Use `echonet_cache` to inspect cached discovery and status data

Control guidance:

- First identify the device type
- Only choose actions supported by that device
- If it fails, check `unsupported_device` or `unsupported_property`

### UPnP

Use UPnP / SSDP tools for LAN devices and IGD routers.

Best for:

- Discovering routers or media devices
- Inspecting UPnP-exposed device information
- Checking or operating IGD port mapping

Notes:

- UPnP may be disabled on the router
- SSDP multicast must work for discovery
- Results can vary depending on the router implementation

Typical flow:

1. Use `upnp_scan` to discover devices
2. Use `upnp_igd_control` to inspect or operate IGD features

### Matter

Use Matter tools for Matter-connected devices.

Best for:

- Inspecting controller / bridge / device structure
- Listing managed devices
- Checking device status
- Inspecting endpoints and clusters

Notes:

- Matter has a layered structure, so keep controller / bridge / device separate
- Read-only tools are currently the main focus
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
- SwitchBot Cloud: `switchbot_cloud_control`
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
