"""A module with only plain top-level functions."""

from __future__ import annotations


def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


def subtract(a: int, b: int) -> int:
    return a - b


def _private_helper(x: int) -> int:
    """Not part of the public API."""
    return x * 2
