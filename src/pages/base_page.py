"""BasePage: shared behaviour for every page object.

Design rules enforced here:

* Every page object owns a ``self.page`` (Playwright ``Page``).
* Public methods describe **user actions** ("search for X", "add to cart"),
  not low-level locator clicks.
* No assertions live in pages or components - assertions belong to tests/flows.
* Locators are encapsulated; tests must never reach into ``page.locator(...)``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from playwright.sync_api import TimeoutError as PlaywrightTimeout

from src.config import get_settings
from src.utils.healing import AriaFallback, HealingResult, find_first_visible
from src.utils.logger import get_logger
from src.utils.screenshot import attach_screenshot

if TYPE_CHECKING:
    from playwright.sync_api import Locator, Page


class BasePage:
    """Foundation for every Page Object."""

    URL_PATH: str = "/"

    # CSS candidates for the "accept cookies" banner. Common patterns across
    # storefronts: OneTrust, generic "Accept all", text-based fallbacks.
    _COOKIE_ACCEPT_SELECTORS: tuple[str, ...] = (
        "#onetrust-accept-btn-handler",
        "button[aria-label='Accept all']",
        "button:has-text('Accept all')",
        "button:has-text('Accept All Cookies')",
        "button:has-text('I Accept')",
        "button:has-text('Got it')",
    )

    # Region/locale or generic interstitial modals. Most specific first.
    # automationexercise.com generally has no such modal, so this is a defensive
    # no-op there; left in place because it costs nothing and helps when we
    # retarget the framework at sites that DO show one.
    _REGION_DISMISS_SELECTORS: tuple[str, ...] = (
        "button:has-text('Stay on this site')",
        "button:has-text('Continue')",
        "button:has-text('Stay')",
        "[aria-label='Close']",
    )

    def __init__(self, page: "Page") -> None:
        self.page = page
        self.settings = get_settings()
        self.log = get_logger(self.__class__.__name__)

    # ------------------------------------------------------------------ navigation
    def open(self, path: str | None = None) -> "BasePage":
        """Navigate to ``BASE_URL + (path or URL_PATH)`` and dismiss banners."""
        target = path if path is not None else self.URL_PATH
        url = target if target.startswith("http") else f"{self.settings.base_url}{target}"
        self.log.info(f"Navigating to {url}")
        self.page.goto(url, wait_until="domcontentloaded")
        self.dismiss_overlays()
        return self

    def reload(self) -> "BasePage":
        self.page.reload(wait_until="domcontentloaded")
        self.dismiss_overlays()
        return self

    @property
    def current_url(self) -> str:
        return self.page.url

    # ---------------------------------------------------------------- overlays
    def dismiss_overlays(self) -> None:
        """Best-effort dismissal of cookie consent and region modals.

        Never raises - if no overlay is present, this is a no-op.

        Per-selector budget is small (300ms) to keep the no-banner path fast:
        on automationexercise.com nothing matches and we'd otherwise burn
        ``len(selectors) * timeout_ms`` waiting for non-existent overlays.
        Sites with slower-mounting modals can override ``dismiss_overlays``
        on the page-object subclass.
        """
        self._click_first_visible(
            self._COOKIE_ACCEPT_SELECTORS, label="cookie consent", timeout_ms=300
        )
        self._click_first_visible(
            self._REGION_DISMISS_SELECTORS, label="region modal", timeout_ms=300
        )

    def _click_first_visible(
        self,
        selectors: tuple[str, ...],
        *,
        label: str,
        timeout_ms: int = 1500,
        aria_fallback: AriaFallback | None = None,
    ) -> bool:
        result = find_first_visible(
            self.page,
            selectors,
            aria_fallback=aria_fallback,
            timeout_ms=timeout_ms,
            label=label,
        )
        if result.locator is None:
            return False
        try:
            result.locator.click(timeout=2000)
            self.log.info(f"Dismissed {label} (healed={result.healed})")
            return True
        except Exception as exc:  # noqa: BLE001
            self.log.debug(f"Click failed for {label}: {exc}")
            return False

    def _first_visible(
        self,
        selectors: tuple[str, ...],
        *,
        label: str = "",
        timeout_ms: int = 1500,
        aria_fallback: AriaFallback | None = None,
    ) -> HealingResult:
        """Find the first visible element from ``selectors``, with ARIA fallback."""
        return find_first_visible(
            self.page,
            selectors,
            aria_fallback=aria_fallback,
            timeout_ms=timeout_ms,
            label=label,
        )

    # ---------------------------------------------------------------- waits
    def wait_for_network_idle(self, timeout_ms: int | None = None) -> None:
        """Wait until network is idle, but don't fail the test if SSE keeps it busy."""
        try:
            self.page.wait_for_load_state(
                "networkidle",
                timeout=timeout_ms or self.settings.navigation_timeout_ms,
            )
        except PlaywrightTimeout:
            self.log.debug("network idle wait timed out (continuing)")

    def wait_for_visible(self, selector: str, *, timeout_ms: int | None = None) -> "Locator":
        locator = self.page.locator(selector).first
        locator.wait_for(state="visible", timeout=timeout_ms or self.settings.action_timeout_ms)
        return locator

    # ---------------------------------------------------------------- artefacts
    def screenshot(self, name: str) -> None:
        """Take a named screenshot and attach to Allure."""
        attach_screenshot(self.page, name)
