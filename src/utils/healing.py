"""Self-healing locator utilities.

When all CSS selector candidates fail, the healing layer falls back to the
browser's **accessibility tree** via Playwright's ``get_by_role``.  The
accessibility tree describes elements by semantic role (button, link,
textbox) and accessible name (visible text, aria-label) — both of which
survive CSS-class renames, ID changes, and most UI redesigns.

Healing events are logged at WARNING level and optionally produce an
Allure-attached screenshot so reviewers can see exactly when and where
the framework healed itself.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, NamedTuple

from playwright.sync_api import TimeoutError as PlaywrightTimeout

from src.utils.logger import get_logger

if TYPE_CHECKING:
    from playwright.sync_api import Locator, Page

_log = get_logger("healing")


class AriaFallback(NamedTuple):
    """Accessibility-tree hint used when all CSS candidates fail.

    ``role`` is the ARIA role string (``"button"``, ``"link"``,
    ``"textbox"``, etc.).  ``name`` is a string or compiled regex
    matched against the element's accessible name.
    """

    role: str
    name: str | re.Pattern[str]


class HealingResult(NamedTuple):
    """Return value from :func:`find_first_visible`."""

    locator: Locator | None
    candidate_index: int
    healed: bool


def find_first_visible(
    page: Page,
    candidates: tuple[str, ...],
    *,
    aria_fallback: AriaFallback | None = None,
    timeout_ms: int = 1500,
    label: str = "",
) -> HealingResult:
    """Try each CSS candidate; fall back to the accessibility tree on miss.

    Returns a :class:`HealingResult` triple so callers know which
    candidate won and whether healing kicked in.
    """
    for idx, selector in enumerate(candidates):
        try:
            locator = page.locator(selector).first
            if locator.is_visible(timeout=timeout_ms):
                if idx > 0:
                    _log.info(
                        f"[{label}] Used candidate #{idx + 1}/{len(candidates)}: "
                        f"{selector!r} (primary was {candidates[0]!r})"
                    )
                return HealingResult(locator=locator, candidate_index=idx, healed=False)
        except PlaywrightTimeout:
            continue
        except Exception as exc:  # noqa: BLE001
            _log.debug(f"[{label}] Candidate {selector!r} raised: {exc}")

    if aria_fallback is not None:
        try:
            locator = page.get_by_role(aria_fallback.role, name=aria_fallback.name).first
            if locator.is_visible(timeout=timeout_ms):
                _log.warning(
                    f"[{label}] HEALED — all {len(candidates)} CSS candidates failed. "
                    f"Resolved via accessibility tree: "
                    f"role={aria_fallback.role!r}, name={aria_fallback.name!r}"
                )
                _attach_healing_evidence(page, label, candidates, aria_fallback)
                return HealingResult(locator=locator, candidate_index=-1, healed=True)
        except PlaywrightTimeout:
            pass
        except Exception as exc:  # noqa: BLE001
            _log.debug(f"[{label}] ARIA fallback raised: {exc}")

    return HealingResult(locator=None, candidate_index=-1, healed=False)


def _attach_healing_evidence(
    page: Page,
    label: str,
    candidates: tuple[str, ...],
    fallback: AriaFallback,
) -> None:
    """Best-effort Allure attachment when healing occurs."""
    try:
        import allure

        from src.utils.screenshot import attach_screenshot

        attach_screenshot(page, f"HEALED_{label}")
        allure.attach(
            f"All CSS candidates failed:\n"
            + "\n".join(f"  [{i + 1}] {s}" for i, s in enumerate(candidates))
            + f"\n\nHealed via accessibility tree:\n"
            f"  role={fallback.role!r}, name={fallback.name!r}",
            name=f"healing_event_{label}",
            attachment_type=allure.attachment_type.TEXT,
        )
    except Exception as exc:  # noqa: BLE001
        _log.debug(f"Could not attach healing evidence: {exc}")
