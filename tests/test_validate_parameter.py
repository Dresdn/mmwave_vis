"""
Tests for validate_parameter() — the whitelist gate before any value is sent
to a device over MQTT/ZHA.

Pattern for every test:
  valid, error = validate_parameter(param, value)
  assert valid is True/False
  assert error is None / "contains some text"
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'mmwave_vis'))

from utils import validate_parameter


# ===========================================================================
# Unknown parameter
# ===========================================================================

def test_unknown_param_rejected():
    valid, error = validate_parameter('notARealParam', 'anything')
    assert valid is False
    assert 'Unknown parameter' in error


# ===========================================================================
# Enum parameters
# ===========================================================================

class TestEnumSensitivity:
    PARAM = 'mmWaveDetectSensitivity'

    def test_valid_low(self):
        valid, error = validate_parameter(self.PARAM, 'Low')
        assert valid is True
        assert error is None

    def test_valid_medium(self):
        valid, error = validate_parameter(self.PARAM, 'Medium')
        assert valid is True

    def test_valid_high_default(self):
        valid, error = validate_parameter(self.PARAM, 'High (default)')
        assert valid is True

    def test_wrong_case_rejected(self):
        valid, error = validate_parameter(self.PARAM, 'low')
        assert valid is False
        assert 'Invalid value' in error

    def test_empty_string_rejected(self):
        valid, error = validate_parameter(self.PARAM, '')
        assert valid is False

    def test_integer_rejected(self):
        # Enum params require a string, not a number
        valid, error = validate_parameter(self.PARAM, 1)
        assert valid is False

    def test_none_rejected(self):
        valid, error = validate_parameter(self.PARAM, None)
        assert valid is False


class TestEnumTrigger:
    PARAM = 'mmWaveDetectTrigger'

    def test_fast(self):
        valid, _ = validate_parameter(self.PARAM, 'Fast (0.2s, default)')
        assert valid is True

    def test_medium(self):
        valid, _ = validate_parameter(self.PARAM, 'Medium (1s)')
        assert valid is True

    def test_slow(self):
        valid, _ = validate_parameter(self.PARAM, 'Slow (5s)')
        assert valid is True

    def test_invalid_option(self):
        valid, error = validate_parameter(self.PARAM, 'Instant')
        assert valid is False
        assert 'Invalid value' in error


class TestEnumTargetInfoReport:
    PARAM = 'mmWaveTargetInfoReport'

    def test_disable(self):
        valid, _ = validate_parameter(self.PARAM, 'Disable (default)')
        assert valid is True

    def test_enable(self):
        valid, _ = validate_parameter(self.PARAM, 'Enable')
        assert valid is True

    def test_random_string(self):
        valid, _ = validate_parameter(self.PARAM, 'Yes')
        assert valid is False


# ===========================================================================
# Integer parameters
# ===========================================================================

class TestIntHoldTime:
    PARAM = 'mmWaveHoldTime'

    def test_zero(self):
        valid, error = validate_parameter(self.PARAM, 0)
        assert valid is True
        assert error is None

    def test_max(self):
        valid, _ = validate_parameter(self.PARAM, 28800)
        assert valid is True

    def test_midpoint(self):
        valid, _ = validate_parameter(self.PARAM, 300)
        assert valid is True

    def test_string_integer(self):
        # The frontend may send integers as strings
        valid, _ = validate_parameter(self.PARAM, '120')
        assert valid is True

    def test_negative_rejected(self):
        valid, error = validate_parameter(self.PARAM, -1)
        assert valid is False
        assert 'out of range' in error

    def test_over_max_rejected(self):
        valid, error = validate_parameter(self.PARAM, 28801)
        assert valid is False
        assert 'out of range' in error

    def test_float_string_rejected(self):
        # "3.5" cannot be int() directly — should fail gracefully
        valid, error = validate_parameter(self.PARAM, '3.5')
        assert valid is False
        assert 'integer' in error

    def test_non_numeric_string_rejected(self):
        valid, error = validate_parameter(self.PARAM, 'forever')
        assert valid is False

    def test_none_rejected(self):
        valid, error = validate_parameter(self.PARAM, None)
        assert valid is False


class TestIntStayLife:
    """mmWaveStayLife has the same range as HoldTime — quick sanity checks."""

    def test_valid(self):
        valid, _ = validate_parameter('mmWaveStayLife', 60)
        assert valid is True

    def test_out_of_range(self):
        valid, _ = validate_parameter('mmWaveStayLife', 99999)
        assert valid is False


# ===========================================================================
# Zone composite parameters
# ===========================================================================

class TestZoneComposite:
    PARAM = 'mmwave_detection_areas'

    def _area(self, **coords):
        """Helper: build a minimal valid area dict."""
        defaults = {
            'width_min': 0, 'width_max': 100,
            'depth_min': 0, 'depth_max': 500,
            'height_min': -200, 'height_max': 200,
        }
        defaults.update(coords)
        return defaults

    def test_valid_single_area(self):
        value = {'area1': self._area()}
        valid, error = validate_parameter(self.PARAM, value)
        assert valid is True
        assert error is None

    def test_valid_four_areas(self):
        value = {f'area{i}': self._area() for i in range(1, 5)}
        valid, _ = validate_parameter(self.PARAM, value)
        assert valid is True

    def test_not_a_dict_rejected(self):
        valid, error = validate_parameter(self.PARAM, 'not a dict')
        assert valid is False
        assert 'dict' in error

    def test_invalid_area_key_rejected(self):
        value = {'zone1': self._area()}  # should be "area1"
        valid, error = validate_parameter(self.PARAM, value)
        assert valid is False
        assert 'Invalid area key' in error

    def test_area_number_zero_rejected(self):
        value = {'area0': self._area()}
        valid, error = validate_parameter(self.PARAM, value)
        assert valid is False
        assert 'out of range' in error

    def test_area_number_five_rejected(self):
        value = {'area5': self._area()}
        valid, error = validate_parameter(self.PARAM, value)
        assert valid is False
        assert 'out of range' in error

    def test_unknown_zone_key_rejected(self):
        area = self._area()
        area['banana'] = 0
        value = {'area1': area}
        valid, error = validate_parameter(self.PARAM, value)
        assert valid is False
        assert 'Unknown zone keys' in error

    def test_coordinate_out_of_range_rejected(self):
        value = {'area1': self._area(width_min=-99999)}
        valid, error = validate_parameter(self.PARAM, value)
        assert valid is False
        assert 'out of range' in error

    def test_coordinate_at_negative_boundary(self):
        value = {'area1': self._area(width_min=-10000)}
        valid, _ = validate_parameter(self.PARAM, value)
        assert valid is True

    def test_coordinate_at_positive_boundary(self):
        value = {'area1': self._area(width_max=10000)}
        valid, _ = validate_parameter(self.PARAM, value)
        assert valid is True

    def test_string_coordinates_accepted(self):
        # Coordinates may arrive as strings from the frontend
        area = {k: str(v) for k, v in self._area().items()}
        value = {'area1': area}
        valid, _ = validate_parameter(self.PARAM, value)
        assert valid is True

    def test_non_integer_coordinate_rejected(self):
        value = {'area1': self._area(width_min='abc')}
        valid, error = validate_parameter(self.PARAM, value)
        assert valid is False
        assert 'integer' in error

    def test_area_value_not_dict_rejected(self):
        value = {'area1': [0, 100, 0, 500]}
        valid, error = validate_parameter(self.PARAM, value)
        assert valid is False
        assert 'must be a dict' in error

    def test_interference_areas_param(self):
        value = {'area2': self._area()}
        valid, _ = validate_parameter('mmwave_interference_areas', value)
        assert valid is True

    def test_stay_areas_param(self):
        value = {'area3': self._area()}
        valid, _ = validate_parameter('mmwave_stay_areas', value)
        assert valid is True
