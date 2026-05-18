"""Price filter widget on the search results page.

Different storefronts expose price filters differently: some are pairs of
``Min`` / ``Max`` text inputs, others are sliders, others are pre-bucketed
checkbox groups (e.g. ``$0-$50``). The component supports the text-input
flavour out of the box and falls back gracefully if no inputs are found
(see ``apply()`` returning ``False``). The search flow then applies the
price constraint client-side.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from playwright.sync_api import TimeoutError as PlaywrightTimeout

from src.utils.healing import AriaFallback, find_first_visible
from src.utils.logger import get_logger

if TYPE_CHECKING:
    from playwright.sync_api import Locator, Page


class PriceFilter:
    """Wraps the min/max price inputs."""

    MIN_INPUT_CANDIDATES: tuple[str, ...] = (
        "input[name='filter.v.price.gte']",
        "input[aria-label*='From' i]",
        "input[placeholder='Min']",
        "input[name*='price' i][name*='min' i]",
    )
    MIN_INPUT_ARIA = AriaFallback(role="textbox", name=re.compile(r"from|min", re.I))

    MAX_INPUT_CANDIDATES: tuple[str, ...] = (
        "input[name='filter.v.price.lte']",
        "input[aria-label*='To' i]",
        "input[placeholder='Max']",
        "input[name*='price' i][name*='max' i]",
    )
    MAX_INPUT_ARIA = AriaFallback(role="textbox", name=re.compile(r"to|max", re.I))

    APPLY_BUTTON_CANDIDATES: tuple[str, ...] = (
        "button:has-text('Apply')",
        "button[type='submit'][aria-label*='price' i]",
    )
    APPLY_BUTTON_ARIA = AriaFallback(role="button", name=re.compile(r"apply", re.I))

    def __init__(self, page: "Page") -> None:
        self.page = page
        self.log = get_logger("PriceFilter")

    def apply(self, min_price: float | None, max_price: float | None) -> bool:
        """Set min/max and submit. Return True if the filter was applied."""
        applied = False
        if min_price is not None:
            applied |= self._fill_first(
                self.MIN_INPUT_CANDIDATES, str(int(min_price)),
                aria_fallback=self.MIN_INPUT_ARIA, label="price-min",
            )
        if max_price is not None:
            applied |= self._fill_first(
                self.MAX_INPUT_CANDIDATES, str(int(max_price)),
                aria_fallback=self.MAX_INPUT_ARIA, label="price-max",
            )

        if not applied:
            self.log.warning("Price filter inputs not found - falling back to client-side filter")
            return False

        self._submit()
        try:
            self.page.wait_for_load_state("networkidle", timeout=8000)
        except PlaywrightTimeout:
            pass
        self.log.info(f"Applied price filter: min={min_price}, max={max_price}")
        return True

    def _fill_first(
        self,
        candidates: tuple[str, ...],
        value: str,
        *,
        aria_fallback: AriaFallback | None = None,
        label: str = "",
    ) -> bool:
        result = find_first_visible(
            self.page, candidates, aria_fallback=aria_fallback, timeout_ms=1000, label=label,
        )
        if result.locator is None:
            return False
        result.locator.click()
        result.locator.fill("")
        result.locator.fill(value)
        result.locator.press("Tab")
        return True

    def _submit(self) -> None:
        result = find_first_visible(
            self.page,
            self.APPLY_BUTTON_CANDIDATES,
            aria_fallback=self.APPLY_BUTTON_ARIA,
            timeout_ms=1000,
            label="price-apply",
        )
        if result.locator is not None:
            result.locator.click()
        else:
            self.page.keyboard.press("Enter")
