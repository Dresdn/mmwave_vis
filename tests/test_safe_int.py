"""
Tests for safe_int() — the utility that converts values to int without crashing.

Each test function is a small, independent scenario. pytest finds them
automatically because their names start with "test_".
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'mmwave_vis'))

from utils import safe_int


# --- Normal conversions ---

def test_integer_passthrough():
    assert safe_int(42) == 42

def test_negative_integer():
    assert safe_int(-7) == -7

def test_string_integer():
    assert safe_int("100") == 100

def test_float_rounds_down():
    # int(float("3.9")) == 3, not 4 — this is the intended behaviour
    assert safe_int("3.9") == 3

def test_float_value():
    assert safe_int(2.7) == 2


# --- Fallback to default ---

def test_none_returns_default():
    assert safe_int(None) == 0

def test_empty_string_returns_default():
    assert safe_int("") == 0

def test_non_numeric_string_returns_default():
    assert safe_int("hello") == 0

def test_list_returns_default():
    assert safe_int([1, 2, 3]) == 0


# --- Custom default value ---

def test_custom_default_on_none():
    assert safe_int(None, default=99) == 99

def test_custom_default_on_bad_string():
    assert safe_int("oops", default=-1) == -1

def test_custom_default_not_used_on_valid():
    assert safe_int("5", default=99) == 5


# --- Edge cases ---

def test_zero():
    assert safe_int(0) == 0

def test_zero_string():
    assert safe_int("0") == 0

def test_large_number():
    assert safe_int(28800) == 28800

def test_negative_string():
    assert safe_int("-500") == -500
