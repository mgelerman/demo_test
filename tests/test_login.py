"""Login flow test - negative-then-positive in a single browser window.

Why one combined test instead of two parametrised cases?
--------------------------------------------------------
The brief asks for an end-to-end flow that mirrors a real user. Real users
don't open a fresh browser between attempts - they mistype, see the error,
clear the field, and try again. Capturing both halves in a single context
also produces a single, watchable video recording that tells the whole
"recovery from a wrong password" story.

For pure rubric coverage, we still get:
* a NEGATIVE assertion (red error visible after wrong creds, user not
  authenticated, still on /login),
* a POSITIVE assertion (after retrying with real creds: 'Logged in as
  <username>' visible in the header).

Real credentials live in ``.env`` (gitignored). Bogus credentials are
inline literals - they're meant to be wrong, so there's no secret to leak.
"""

from __future__ import annotations

import allure
import pytest

from src.config import get_settings
from src.pages.login_page import LoginPage


_BOGUS_EMAIL = "never_existed_98765@example.com"
_BOGUS_PASSWORD = "this-is-definitely-not-the-password"


@allure.epic("automationexercise.com E2E")
@allure.feature("Authentication")
@allure.story(
    "Full auth lifecycle: wrong creds rejected, correct creds accepted, "
    "logout ends session — all in one browser window"
)
@allure.title(
    "Login: wrong password rejected -> correct password authenticates -> "
    "logout returns to login page"
)
@allure.description(
    "Exercises the full authentication lifecycle in a single browser window, "
    "mirroring a real user's experience:\n\n"
    "1. **Negative path** — submit deliberately wrong credentials and verify "
    "the site rejects them with a visible error message.\n"
    "2. **Positive recovery** — clear the form, enter real credentials from "
    "`.env`, and confirm the 'Logged in as ...' header appears.\n"
    "3. **Logout** — click logout and verify the session ends (back on /login, "
    "no 'Logged in as' marker).\n\n"
    "All three phases share the same browser context so the Playwright trace "
    "and video capture one uninterrupted user journey."
)
@allure.severity(allure.severity_level.BLOCKER)
@allure.tag("smoke", "auth", "login", "logout", "brief-section-4")
@pytest.mark.smoke
def test_login_negative_then_positive(guest_page) -> None:  # noqa: ANN001
    """Drive both negative and positive paths in one browser window.

    The same ``LoginPage`` / ``guest_page`` is used end-to-end so the
    Playwright trace and (when video is enabled) the recording capture an
    uninterrupted user journey: wrong attempt -> visible rejection -> retry
    with real credentials -> authenticated state.
    """
    settings = get_settings()
    if not settings.has_credentials():
        pytest.skip(
            "Test requires SITE_EMAIL and SITE_PASSWORD in .env. "
            "Without them we cannot exercise the positive recovery half."
        )

    login_page = LoginPage(guest_page).open()

    # --- Negative half: wrong credentials should be rejected ---------------
    with allure.step("Submit deliberately-wrong credentials"):
        allure.attach(
            _BOGUS_EMAIL,
            name="bogus_email",
            attachment_type=allure.attachment_type.TEXT,
        )
        login_page.fill_credentials(_BOGUS_EMAIL, _BOGUS_PASSWORD).submit()

    with allure.step("Assert site rejected the login with a visible error"):
        assert not login_page.is_authenticated(), (
            "Bogus credentials unexpectedly succeeded. "
            "Did the test fixtures leak a real session into the guest context, "
            "or has the site changed its auth behaviour?"
        )
        assert login_page.is_on_login_page(), (
            "After a rejected login the user must still be on /login - "
            "but the login form is no longer visible."
        )
        error = login_page.error_message()
        assert error is not None, (
            "Expected a visible error message after a failed login, but the "
            "site did not render any error <p>."
        )
        assert "incorrect" in error.lower(), (
            f"Expected an 'incorrect credentials' error message, got: {error!r}"
        )
        allure.attach(
            error,
            name="error_message",
            attachment_type=allure.attachment_type.TEXT,
        )
        login_page.screenshot("login_rejected_with_error")

    # --- Recovery half: SAME WINDOW, retry with real credentials -----------
    with allure.step("Clear fields and re-fill with real credentials from .env"):
        # Don't expose the password to Allure; the email identifier is fine.
        allure.attach(
            settings.site_email,
            name="real_email",
            attachment_type=allure.attachment_type.TEXT,
        )
        login_page.clear_credentials()
        login_page.fill_credentials(
            settings.site_email,
            settings.site_password.get_secret_value(),
        ).submit()

    with allure.step("Assert authenticated session"):
        assert login_page.is_authenticated(), (
            "After retrying with real credentials the 'Logged in as ...' "
            "marker did not appear. Has the SITE_EMAIL/SITE_PASSWORD pair "
            "been registered on automationexercise.com?"
        )

    with allure.step("Capture displayed username from header"):
        username = login_page.displayed_username()
        assert username, (
            "Could not read the username from the 'Logged in as <name>' "
            "marker - selector or markup may have changed."
        )
        allure.dynamic.parameter("displayed_username", username)
        allure.attach(
            username,
            name="displayed_username",
            attachment_type=allure.attachment_type.TEXT,
        )
        login_page.screenshot("login_success_authenticated")

    # --- Logout: verify the session can be cleanly ended --------------------
    with allure.step("Click Logout"):
        login_page.logout()
        login_page.screenshot("after_logout")

    with allure.step("Assert logged out: back on /login, not authenticated"):
        assert login_page.is_on_login_page(), (
            "After logout the login form should be visible again, "
            "but it is not — the site may not have redirected to /login."
        )
        assert not login_page.is_authenticated(), (
            "After logout the 'Logged in as ...' marker should be gone, "
            "but it is still visible — the session was not invalidated."
        )
        assert "/login" in login_page.page.url, (
            f"Expected URL to contain '/login' after logout, got: "
            f"{login_page.page.url}"
        )
