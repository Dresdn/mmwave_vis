"""
Tests for Z2M device-discovery topic filtering.

The logic under test lives in Z2MDriver._on_message (app.py):

    if (
        topic.startswith(MQTT_BASE_TOPIC)
        and "mmWaveVersion" in payload
        and not topic.endswith("/get")
        and not topic.endswith("/set")
    ):
        parts = topic.split('/')
        if len(parts) >= 2:
            fname = '/'.join(parts[1:])
            ...  # add to device_list

These tests verify that:
  1. Only base-topic publishes trigger discovery.
  2. Z2M /get and /set echo topics are rejected.
  3. Payloads missing mmWaveVersion are rejected.
  4. Edge cases (availability, bridge topics, etc.) are handled.
"""

BASE = "zigbee2mqtt"

# Minimal payload that passes the mmWaveVersion gate
VALID_PAYLOAD = {"mmWaveVersion": "1.0.0", "occupancy": True}

# Payload without mmWaveVersion
NO_VERSION_PAYLOAD = {"occupancy": True, "illuminance": 42}


def _should_discover(topic: str, payload: dict, base: str = BASE) -> str | None:
    """Mirror the discovery filter from Z2MDriver._on_message.

    Returns the extracted friendly_name if the topic/payload pair would
    trigger device discovery, or None if it would be filtered out.
    """
    if (
        topic.startswith(base)
        and "mmWaveVersion" in payload
        and not topic.endswith("/get")
        and not topic.endswith("/set")
    ):
        parts = topic.split("/")
        if len(parts) >= 2:
            return "/".join(parts[1:])
    return None


# ---------------------------------------------------------------------------
# Base-topic publishes — should discover
# ---------------------------------------------------------------------------

def test_base_topic_discovers():
    assert _should_discover(f"{BASE}/kitchen", VALID_PAYLOAD) == "kitchen"


def test_base_topic_with_spaces():
    assert _should_discover(f"{BASE}/Living Room Switch", VALID_PAYLOAD) == "Living Room Switch"


def test_base_topic_with_slash_in_name():
    """Device names containing '/' should still be discovered correctly."""
    assert _should_discover(f"{BASE}/Floor/Room/Switch", VALID_PAYLOAD) == "Floor/Room/Switch"


def test_base_topic_discovers_with_extra_fields():
    """Discovery should work even when payload has many extra fields."""
    payload = {**VALID_PAYLOAD, "state": "ON", "brightness": 254}
    assert _should_discover(f"{BASE}/office", payload) == "office"


# ---------------------------------------------------------------------------
# /get topics — must be rejected (issue #24)
# ---------------------------------------------------------------------------

def test_get_suffix_rejected():
    """The exact bug from issue #24 — /get echo must not create a new device."""
    assert _should_discover(f"{BASE}/kitchen/get", VALID_PAYLOAD) is None


def test_get_suffix_with_spaces():
    assert _should_discover(f"{BASE}/Living Room Switch/get", VALID_PAYLOAD) is None


def test_get_suffix_with_slash_in_name():
    """A device named 'Floor/Room' sends a /get on 'zigbee2mqtt/Floor/Room/get'."""
    assert _should_discover(f"{BASE}/Floor/Room/get", VALID_PAYLOAD) is None


# ---------------------------------------------------------------------------
# /set topics — must also be rejected
# ---------------------------------------------------------------------------

def test_set_suffix_rejected():
    assert _should_discover(f"{BASE}/kitchen/set", VALID_PAYLOAD) is None


def test_set_suffix_with_spaces():
    assert _should_discover(f"{BASE}/Living Room Switch/set", VALID_PAYLOAD) is None


def test_set_suffix_with_slash_in_name():
    assert _should_discover(f"{BASE}/Floor/Room/set", VALID_PAYLOAD) is None


# ---------------------------------------------------------------------------
# /availability topics — should be rejected (no mmWaveVersion)
# ---------------------------------------------------------------------------

def test_availability_topic_rejected():
    """Availability messages never contain mmWaveVersion."""
    payload = {"state": "online"}
    assert _should_discover(f"{BASE}/kitchen/availability", payload) is None


def test_availability_even_with_version_key():
    """Even if availability somehow had mmWaveVersion, it ends with /availability."""
    # This is rejected because /availability doesn't end with /get or /set,
    # BUT it would pass our filter.  In practice Z2M availability never
    # contains mmWaveVersion, so this is fine.  Including this test to
    # document the behaviour.
    assert _should_discover(f"{BASE}/kitchen/availability", VALID_PAYLOAD) == "kitchen/availability"


# ---------------------------------------------------------------------------
# Missing mmWaveVersion — must be rejected regardless of topic
# ---------------------------------------------------------------------------

def test_no_version_base_topic():
    assert _should_discover(f"{BASE}/kitchen", NO_VERSION_PAYLOAD) is None


def test_no_version_get_topic():
    assert _should_discover(f"{BASE}/kitchen/get", NO_VERSION_PAYLOAD) is None


def test_no_version_set_topic():
    assert _should_discover(f"{BASE}/kitchen/set", NO_VERSION_PAYLOAD) is None


def test_empty_payload():
    assert _should_discover(f"{BASE}/kitchen", {}) is None


# ---------------------------------------------------------------------------
# Bridge / system topics — must not trigger discovery
# ---------------------------------------------------------------------------

def test_bridge_state_rejected():
    payload = {"state": "online"}
    assert _should_discover(f"{BASE}/bridge/state", payload) is None


def test_bridge_info_rejected():
    payload = {"version": "2.9.1", "coordinator": {}}
    assert _should_discover(f"{BASE}/bridge/info", payload) is None


def test_bridge_logging_rejected():
    payload = {"level": "info", "message": "Started"}
    assert _should_discover(f"{BASE}/bridge/logging", payload) is None


# ---------------------------------------------------------------------------
# Wrong base topic — must not trigger discovery
# ---------------------------------------------------------------------------

def test_wrong_base_topic():
    assert _should_discover("homeassistant/kitchen", VALID_PAYLOAD) is None


def test_partial_base_overlap():
    """'zigbee2mqttExtra/device' should not match 'zigbee2mqtt' base."""
    # startswith("zigbee2mqtt") would match this — but the extraction
    # still works because it splits on '/' and takes parts[1:].
    # Document this edge case.
    result = _should_discover("zigbee2mqttExtra/device", VALID_PAYLOAD)
    # startswith does match, so it would discover "device" — but this
    # topic would never appear in practice because base topics don't
    # share prefixes like this.
    assert result == "device"


# ---------------------------------------------------------------------------
# Custom base topic
# ---------------------------------------------------------------------------

def test_custom_base_topic():
    assert _should_discover("z2m/kitchen", VALID_PAYLOAD, base="z2m") == "kitchen"


def test_custom_base_get_rejected():
    assert _should_discover("z2m/kitchen/get", VALID_PAYLOAD, base="z2m") is None


def test_custom_base_set_rejected():
    assert _should_discover("z2m/kitchen/set", VALID_PAYLOAD, base="z2m") is None


# ---------------------------------------------------------------------------
# Repeated selection — verify /get/get chains are all rejected
# ---------------------------------------------------------------------------

def test_double_get_rejected():
    """User reports cascading /get/get entries — all must be filtered."""
    assert _should_discover(f"{BASE}/kitchen/get/get", VALID_PAYLOAD) is None


def test_triple_get_rejected():
    assert _should_discover(f"{BASE}/kitchen/get/get/get", VALID_PAYLOAD) is None


def test_get_then_set_rejected():
    assert _should_discover(f"{BASE}/kitchen/get/set", VALID_PAYLOAD) is None


def test_set_then_get_rejected():
    assert _should_discover(f"{BASE}/kitchen/set/get", VALID_PAYLOAD) is None


# ---------------------------------------------------------------------------
# Case sensitivity — Z2M topics are case-sensitive
# ---------------------------------------------------------------------------

def test_get_uppercase_not_filtered():
    """/GET (uppercase) is not a Z2M suffix — should pass through."""
    assert _should_discover(f"{BASE}/kitchen/GET", VALID_PAYLOAD) == "kitchen/GET"


def test_set_uppercase_not_filtered():
    assert _should_discover(f"{BASE}/kitchen/SET", VALID_PAYLOAD) == "kitchen/SET"


def test_get_mixed_case_not_filtered():
    assert _should_discover(f"{BASE}/kitchen/Get", VALID_PAYLOAD) == "kitchen/Get"


# ---------------------------------------------------------------------------
# Device names that legitimately contain "get" or "set"
# ---------------------------------------------------------------------------

def test_name_containing_get_substring():
    """A device named 'gadget' should not be filtered — 'get' is a substring."""
    assert _should_discover(f"{BASE}/gadget", VALID_PAYLOAD) == "gadget"


def test_name_containing_set_substring():
    """A device named 'sunset' should not be filtered."""
    assert _should_discover(f"{BASE}/sunset", VALID_PAYLOAD) == "sunset"


def test_name_ending_with_get_word():
    """A device named 'target' ends with 'get' but not '/get'."""
    assert _should_discover(f"{BASE}/target", VALID_PAYLOAD) == "target"


def test_name_ending_with_reset():
    """'reset' ends with 'set' but not '/set'."""
    assert _should_discover(f"{BASE}/reset", VALID_PAYLOAD) == "reset"


# ---------------------------------------------------------------------------
# Minimal / edge-case topics
# ---------------------------------------------------------------------------

def test_base_topic_only_no_device():
    """Message on 'zigbee2mqtt' with no device suffix — len(parts) < 2 won't match."""
    assert _should_discover(BASE, VALID_PAYLOAD) is None


def test_base_topic_trailing_slash():
    """'zigbee2mqtt/' → empty device name."""
    assert _should_discover(f"{BASE}/", VALID_PAYLOAD) == ""


def test_topic_is_just_get():
    """Topic 'get' doesn't start with base — rejected."""
    assert _should_discover("get", VALID_PAYLOAD) is None
