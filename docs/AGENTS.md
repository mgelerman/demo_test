# AGENTS.md

> Universal playbook for any AI agent working in this repo. Optimised for
> Cursor but valid for any tool that respects the [agents.md](https://agents.md)
> convention.

## What this project is

End-to-end automation for **automationexercise.com** built on **Python 3.11+,
Playwright (sync), pytest**, with **Allure** reporting and **YAML
data-driven** inputs. The primary deliverables are four user-flow
functions (`login`, `search_items_by_name_under_price`,
`add_items_to_cart`, `assert_cart_total_not_exceeds`) wrapped in a clean
Page Object Model.

## Setup commands

```bash
python -m venv .venv
.venv\Scripts\activate                  # Windows PowerShell
# or: source .venv/bin/activate          # macOS/Linux
pip install -e .[dev]
playwright install chromium
copy .env.example .env                   # Windows
# cp .env.example .env                   # macOS/Linux
```

Edit `.env` to set `SITE_EMAIL`, `SITE_PASSWORD`, and `PROFILE`.

## Test commands

```bash
pytest                                       # full run, Allure results in reports/
pytest -m smoke                              # fast sanity only
pytest -m "search and not e2e"               # search-only data-driven cases
pytest tests/test_e2e_purchase_flow.py -v    # the headline scenario
pytest -k price_parser                       # unit tests, no browser needed
HEADED=true pytest tests/test_e2e_purchase_flow.py   # watch the browser

# View the Allure report (requires the allure CLI on PATH):
allure serve reports/allure-results
```

## Architecture

```
tests/         pytest cases (assertions live here, nowhere else)
src/flows/     the 4 brief functions; orchestrate page objects
src/pages/     Page Object Model (one class per page, extends BasePage)
src/components/  reusable widgets (header, price filter, paginator, product card)
src/utils/     cross-cutting helpers (price parser, screenshot, logger, variant picker)
src/config/    pydantic-settings; profile-based site configuration
data/          YAML inputs for data-driven tests
auth/          storage_state.json after first live login (gitignored)
reports/       allure-results + JUnit XML (gitignored)
screenshots/   per-step captures (gitignored)
```

## Coding conventions

Detailed rules live in `.cursor/rules/*.mdc` and apply automatically in Cursor:

- `00-project-overview.mdc` - layer responsibilities (always loaded).
- `10-python-style.mdc` - Python style and quality (`**/*.py`).
- `20-playwright-pom.mdc` - POM and Playwright rules (`src/pages/**`, `src/components/**`).
- `30-test-authoring.mdc` - pytest conventions (`tests/**`).
- `40-locator-strategy.mdc` - smart-locator selection (`src/pages/**`, `src/components/**`).

Hard-line rules:

- **Decimals, not floats**, for all money math.
- **No `time.sleep`** in `src/`.
- **No assertions** in pages or components - assertions live in tests/flows.
- **Pages do not import other pages.** Cross-page orchestration lives in `src/flows/`.
- **Locator priority**: role -> data-testid -> text -> CSS attr -> XPath. The brief mandates XPath in `SearchResultsPage.PRODUCT_CARD_XPATH` (only).
- **Credentials** never appear in code; only `.env`.

## Common pitfalls (from real failures while building this)

- **Cookie consent / banner overlays** can block clicks. `BasePage.dismiss_overlays()` handles them. Always `open()` via `BasePage`, never `page.goto(...)` directly in flows.
- **automationexercise.com login** uses `data-qa` attributes (`login-email`, `login-password`, `login-button`). They're stable. Submission keeps you on `/login` if credentials are wrong; success redirects to `/` and the header shows `Logged in as <name>`.
- **Sold-out items** can appear in search results. `ProductCard.is_purchasable` filters them out before we send URLs to `add_items_to_cart`.
- **Paginator** must check both visibility AND `aria-disabled="true"` - some themes show the Next button greyed out instead of hiding it.
- **Cart subtotal** has three fallback strategies (tagged selector -> class-name scan -> text scan). Don't simplify this; the markup varies between cart states.

## Adding a new page

Use the slash command: `/add-page-object`. Or manually:

1. Create `src/pages/<name>_page.py` extending `BasePage`.
2. Add selector candidates as class-level UPPER_SNAKE tuples.
3. Public methods describe **user actions** (no generic `click_button`).
4. Re-export from `src/pages/__init__.py`.

## Adding a new test

Use the slash command: `/add-test-case`. Or manually:

1. Drop into the right `tests/test_<area>_*.py`.
2. Use the `page` fixture (or `guest_page`).
3. Call into `src/flows/`; never instantiate page objects in a test.
4. Wrap phases in `with allure.step("...")` and pick at least one `@pytest.mark.<x>`.

## Personas (advanced)

For role-specific reviews and authoring, paste one of these into the chat as a system prompt:

- `docs/personas/qa-architect.md` - architectural reviews, SRP/cohesion criticism.
- `docs/personas/test-engineer.md` - turning acceptance criteria into pytest cases.
- `docs/personas/code-reviewer.md` - PR reviews against the rules above.

## MCP (advanced)

`.cursor/mcp.json` enables the **Playwright MCP** (live browser for locator
discovery) and a repo-scoped **Filesystem MCP**. Use them via the
`/debug-failing-locator` command when a selector breaks. They are optional
augmentations - the test suite runs without them.

## Out of scope (this branch)

- The "AI bugs" review exercise (section 5 of the brief) is a separate
  code-review task and is not part of this repository.
