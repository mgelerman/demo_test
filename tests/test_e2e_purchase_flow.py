"""End-to-end purchase flow on automationexercise.com.

This is the headline scenario from the brief: login -> search -> add to cart
-> assert total. It chains the four required functions exactly as the
brief's example shows.

Login is delivered as a fixture precondition (``logged_in_page``) rather
than inlined in the test body so the test reads as the business flow,
not the plumbing. The fixture's Allure step is "Precondition: log in
with real credentials"; the test's own steps start from step 1 below.

automationexercise.com specifics that shape the test
----------------------------------------------------
* The catalogue uses INR ("Rs.") prices - typical t-shirts are ~Rs. 500
  so a budget of Rs. 1500/item gives plenty of matches without being
  trivially permissive.
* No UI price filter and no real pagination on search results, so the
  search flow filters client-side and stops after page 1; both behaviours
  are documented in :mod:`src.flows.search_flow` and
  :mod:`src.pages.search_results_page`.
"""

from __future__ import annotations

import allure
import pytest

from src.flows import (
    add_items_to_cart,
    assert_cart_total_not_exceeds,
    search_items_by_name_under_price,
)
from src.pages.cart_page import CartPage
from src.pages.checkout_page import CheckoutPage


@allure.epic("automationexercise.com E2E")
@allure.feature("Purchase flow")
@allure.title(
    "End-to-end purchase flow: logged-in search -> add to cart -> "
    "assert cart total -> verify checkout summary"
)
@allure.description(
    "The headline scenario from the exercise brief — chains all four required "
    "functions in a single logged-in session:\n\n"
    "0. **Clear cart** — remove any stale server-side items.\n"
    "1. **Search** — find up to 5 't-shirt' products priced <= Rs. 1500 "
    "(brief section 4.1).\n"
    "2. **Add to cart** — open each PDP, click Add to cart, return to search "
    "(brief section 4.2).\n"
    "3. **Assert total** — verify cart subtotal does not exceed budget * items "
    "(brief section 4.3).\n"
    "4. **Checkout summary** — navigate to /checkout and verify addresses, "
    "line items, total, and Place Order button.\n\n"
    "All money values use `Decimal` arithmetic; prices are parsed by "
    "`PriceParser` from the INR ('Rs.') format."
)
@allure.severity(allure.severity_level.CRITICAL)
@allure.tag(
    "e2e", "purchase-flow", "search", "cart", "checkout",
    "brief-section-4-1", "brief-section-4-2", "brief-section-4-3",
)
@allure.story("Logged-in user: search, add to cart, assert subtotal")
@pytest.mark.e2e
def test_full_purchase_flow_under_budget(logged_in_page) -> None:  # noqa: ANN001
    """Search -> add to cart -> assert subtotal, all in one logged-in session."""
    page = logged_in_page
    query = "tshirt"
    budget_per_item = 1500.0
    limit = 5

    with allure.step("0. Ensure the cart is empty (clear stale server-side items)"):
        cart = CartPage(page).open()
        cart.delete_all_items()

    with allure.step(f"1. Find up to {limit} '{query}' priced <= Rs.{budget_per_item}"):
        urls = search_items_by_name_under_price(page, query, budget_per_item, limit)
        assert isinstance(urls, list), "search_items_by_name_under_price must return a list"

    if not urls:
        pytest.skip(
            "No items matched the price condition - the catalogue may have "
            "shifted. Cannot exercise add-to-cart with zero matches."
        )

    with allure.step(f"2. Add {len(urls)} items to the cart"):
        added = add_items_to_cart(page, urls)
        assert added > 0, "Expected at least one item to be added to the cart."

    with allure.step("3. Assert cart subtotal does not exceed budget * count"):
        cart_subtotal = assert_cart_total_not_exceeds(page, budget_per_item, added)

    with allure.step("4. Proceed to checkout and verify the summary page"):
        CartPage(page).proceed_to_checkout()
        checkout = CheckoutPage(page)

        assert checkout.has_review_heading(), (
            "/checkout: 'Review Your Order' heading not visible"
        )
        assert checkout.has_address_heading(), (
            "/checkout: 'Address Details' heading not visible"
        )
        assert checkout.has_delivery_address(), (
            "/checkout: delivery address block missing"
        )
        assert checkout.has_billing_address(), (
            "/checkout: billing address block missing"
        )
        assert checkout.has_place_order_button(), (
            "/checkout: 'Place Order' button not visible"
        )

        checkout_lines = checkout.line_item_count()
        assert checkout_lines == added, (
            f"/checkout shows {checkout_lines} items but we added {added}"
        )

        checkout_total = checkout.get_total()
        assert checkout_total == cart_subtotal, (
            f"/checkout total ({checkout_total}) != cart subtotal "
            f"({cart_subtotal})"
        )

        threshold = budget_per_item * added
        assert float(checkout_total) <= threshold, (
            f"/checkout total {checkout_total} exceeds "
            f"{budget_per_item} * {added} = {threshold}"
        )
        checkout.screenshot("checkout_review_your_order")
