"""MQTT shared resources: client management (TLS supported)."""

from __future__ import annotations

import ssl
import threading
import time
from typing import Any, Callable
from uuid import uuid4

_CLIENTS: dict[str, dict[str, Any]] = {}
_CLIENTS_LOCK = threading.Lock()
_DEFAULT_QOS = 0


def _paho_import():
    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        from .._pip_auto import install_with_status as _install_mqtt

        if not _install_mqtt("paho-mqtt"):
            raise ImportError("paho-mqtt library could not be installed.")
        import paho.mqtt.client as mqtt
    return mqtt


def create_client(client_id: str | None = None, clean_session: bool = True) -> Any:
    """Create an MQTT client instance."""
    mqtt = _paho_import()
    cid = client_id or f"uag_{int(time.time())}_{uuid4().hex[:6]}"
    client = mqtt.Client(client_id=cid, clean_session=clean_session)
    return client


def connect(
    client: Any,
    host: str,
    port: int = 1883,
    timeout: int = 10,
    username: str = "",
    password: str = "",
    use_tls: bool = False,
    insecure: bool = False,
) -> None:
    """Connect to an MQTT broker. Supports TLS (MQTTS) when use_tls=True."""
    if username:
        client.username_pw_set(username, password)
    if use_tls:
        if insecure:
            client.tls_set(cert_reqs=ssl.CERT_NONE)
            client.tls_insecure_set(True)
        else:
            client.tls_set()
    client.connect(host, port, timeout)
    client.loop_start()


def disconnect(client: Any) -> None:
    """Disconnect from MQTT broker."""
    try:
        client.loop_stop()
        client.disconnect()
    except Exception:
        pass


def publish(
    client: Any, topic: str, payload: str, qos: int = 0, retain: bool = False
) -> dict[str, Any]:
    """Publish a message to an MQTT topic."""
    info = client.publish(topic, payload, qos=qos, retain=retain)
    return {
        "ok": info.rc == 0,
        "mid": info.mid,
        "topic": topic,
        "payload": payload,
        "qos": qos,
        "retain": retain,
    }


def subscribe(
    client: Any,
    topic: str,
    qos: int = 0,
    callback: Callable[[str, str], None] | None = None,
) -> dict[str, Any]:
    """Subscribe to an MQTT topic."""
    if callback:
        client.message_callback_add(
            topic, lambda cl, ud, msg: callback(msg.topic, msg.payload.decode("utf-8"))
        )
    result = client.subscribe(topic, qos)
    return {
        "ok": result[0] == 0,
        "mid": result[1],
        "topic": topic,
        "qos": qos,
    }


def unsubscribe(client: Any, topic: str) -> dict[str, Any]:
    """Unsubscribe from an MQTT topic."""
    result = client.unsubscribe(topic)
    return {"ok": result[0] == 0, "mid": result[1], "topic": topic}
