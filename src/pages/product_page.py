"""Product detail page (PDP) POM for automationexercise.com.

PDP URL pattern: ``/product_details/<id>``.

Surface used by the cart flow:
* No size / colour variants on this site - the only product-level input is
  a quantity field (``#quantity``). :meth:`select_random_in_stock_size`
  becomes a no-op that returns ``None`` (kept for cross-storefront API
  compatibility with the brief).
* :meth:`add_to_cart` clicks ``button.cart`` and dismisses the
  ``#cartModal`` confirmation that opens after every successful add.
"""

from __future__ import annotations

from playwright.sync_api import TimeoutError as PlaywrightTimeout

from src.pages.base_page import BasePage
from src.utils.healing import AriaFallback


class ProductPage(BasePage):
    """Wraps ``/product_details/<id>``."""

    QUANTITY_INPUT = "#quantity"

    ADD_TO_CART_CANDIDATES: tuple[str, ...] = (
        "button.cart",
        "button.btn.btn-default.cart",
        "button:has-text('Add to cart')",
    )
    ADD_TO_CART_ARIA = AriaFallback(role="button", name="Add to cart")

    # Modal that opens after a successful add-to-cart click.
    POST_ADD_MODAL = "#cartModal"
    POST_ADD_DIALOG_CLOSE: tuple[str, ...] = (
        "#cartModal button.close-modal",
        "#cartModal button:has-text('Continue Shopping')",
        "button.close-modal",
    )
    POST_ADD_DIALOG_ARIA = AriaFallback(role="button", name="Continue Shopping")

    PRODUCT_NAME = ".product-information h2"
    PRODUCT_PRICE = ".product-information span span"

    # ---------------------------------------------------------------- navigation
    def open_url(self, url: str) -> "ProductPage":
        """Navigate to a fully-qualified PDP URL."""
        self.open(url)
        try:
            self.page.locator(self.PRODUCT_NAME).first.wait_for(
                state="visible", timeout=8_000
            )
        except PlaywrightTimeout:
            self.log.warning(f"PDP heading did not appear within 8s for {url}")
        return self

    # ------------------------------------------------------------------ variants
    def has_size_picker(self) -> bool:
        """automationexercise.com PDPs have no size/colour selector."""
        return False

    def select_random_in_stock_size(self) -> str | None:
        """No-op for parity with multi-variant storefronts."""
        return None

    # ---------------------------------------------------------------- add to cart
    def add_to_cart(self) -> bool:
        """Click ``Add to cart`` and dismiss the confirmation modal."""
        result = self._first_visible(
            self.ADD_TO_CART_CANDIDATES,
            label="add-to-cart",
            timeout_ms=2000,
            aria_fallback=self.ADD_TO_CART_ARIA,
        )
        if result.locator is None:
            self.log.error("Add-to-cart button not found on this PDP")
            return False
        try:
            result.locator.scroll_into_view_if_needed()
            result.locator.click()
            self.log.info(f"Clicked Add-to-cart (healed={result.healed})")
            self._wait_for_post_add_modal()
            self._dismiss_post_add_dialog()
            return True
        except PlaywrightTimeout:
            self.log.error("Add-to-cart click timed out")
            return False

    def _wait_for_post_add_modal(self) -> None:
        """Wait briefly for the confirmation modal so the next click lands."""
        try:
            self.page.locator(self.POST_ADD_MODAL).first.wait_for(
                state="visible", timeout=4_000
            )
        except PlaywrightTimeout:
            self.log.warning("Post-add modal did not appear within 4s")

    def _dismiss_post_add_dialog(self) -> None:
        """Close the cart modal so subsequent navigation isn't blocked."""
        self._click_first_visible(
            self.POST_ADD_DIALOG_CLOSE,
            label="post-add-dialog",
            timeout_ms=2000,
            aria_fallback=self.POST_ADD_DIALOG_ARIA,
        )
        # As a last resort, press Escape - covers any rare modal variant.
        try:
            self.page.keyboard.press("Escape")
        except Exception:  # noqa: BLE001
            pass
