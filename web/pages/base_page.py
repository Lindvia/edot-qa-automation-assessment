from abc import ABC, abstractmethod
from typing import Optional, Pattern, Union

import allure
from playwright.sync_api import Locator, Page


class BasePage(ABC):
    """Parent of every page object (mirrors the provider-dashboard BasePage).

    Cross-page behaviour (navigation, reload, screenshots, get_by_* shortcuts)
    lives here and is not duplicated per page. Deliberately NOT ported from the
    provider suite: wait_for_timeout (the eDOT brief bans sleeps) and
    wait_for_network_idle (use expect() auto-waiting on a real element instead).

    Locator priority (eDOT brief): data-testid > role + accessible name >
    stable attribute (name / id / aria-*) > text, with a comment justifying
    text. eSuite exposes no data-testid, so role / placeholder / text remain.
    """

    page_path: str = "/"  # relative to base_url; drives visit()

    def __init__(self, page: Page):
        self._page = page
        self.event: Optional[str] = None

    @abstractmethod
    def is_ready(self) -> None:
        """Assert the page's key elements are visible. Call right after visit()."""

    def visit(self) -> None:
        with allure.step(f"Visit {self.page_path}"):
            self._page.goto(self.page_path)
        self.log_event(f"Visited: {self.page_path}")

    def reload(self) -> None:
        self._page.reload()
        self.is_ready()

    def log_event(self, event: str) -> None:
        """Remember the last meaningful step; screenshot() labels itself with it."""
        self.event = event

    def screenshot(self, event: Optional[str] = None) -> None:
        allure.attach(
            self._page.screenshot(),
            name=event or f"Event: {self.event}",
            attachment_type=allure.attachment_type.PNG,
        )

    # --- locator shortcuts -------------------------------------------------
    def get_by_text(self, text: Union[str, Pattern[str]], exact: bool = False) -> Locator:
        return self._page.get_by_text(text, exact=exact)

    def get_by_test_id(self, test_id: str) -> Locator:
        return self._page.get_by_test_id(test_id)

    def get_by_role(self, role: str, name: Union[str, Pattern[str], None] = None, **options) -> Locator:
        return self._page.get_by_role(role, name=name, **options)  # type: ignore[arg-type]

    def get_by_placeholder(self, text: Union[str, Pattern[str]], exact: bool = False) -> Locator:
        return self._page.get_by_placeholder(text, exact=exact)

    def get_by_alt_text(self, text: Union[str, Pattern[str]], exact: bool = False) -> Locator:
        return self._page.get_by_alt_text(text, exact=exact)
