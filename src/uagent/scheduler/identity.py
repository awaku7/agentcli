from __future__ import annotations

from uuid import uuid4

# One opaque owner per Python process. It must not be persisted or reused after
# restart: persisted schedules with this owner become orphaned until reclaimed.
_INSTANCE_ID = str(uuid4())


def scheduler_instance_id() -> str:
    """Return the opaque scheduler owner ID for this UAG process."""
    return _INSTANCE_ID
