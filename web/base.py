"""Single import point for specs (the tests/base.ts of the provider suite).

    from web.base import expect
"""

from playwright.sync_api import expect

__all__ = ["expect"]
