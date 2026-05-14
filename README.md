# E-commerce E2E - Playwright + pytest (POM, OOP, Data-Driven)

End-to-end automation framework targeting
[automationexercise.com](https://www.automationexercise.com).
Implements the four functions required by the exercise brief
(`login`, `search_items_by_name_under_price`, `add_items_to_cart`,
`assert_cart_total_not_exceeds`) plus a checkout-summary verification,
over a clean Page Object Model with typed configuration, YAML-driven
inputs, and Allure reporting.

> **Status:** all five tests pass on `main`. The full brief
> (sections 4.1–4.3) is covered including the checkout page.
> CI runs automatically on every push via GitHub Actions.
> See the latest run in the **Actions** tab.

> The full exercise brief in English is available as a one-page dashboard:
> [`exercise-brief.html`](docs/exercise-brief.html).

> A per-test assertion reference is available in
> [`test-assertions.md`](docs/test-assertions.md) /
> [`test-assertions.html`](docs/test-assertions.html) — **35 assertions**
> across all tests.

## Table of contents

- [Prerequisites](#prerequisites)
- [Setup](#setup)
- [Environment variables](#environment-variables)
- [Security & credentials](#security--credentials)
- [Running the tests](#running-the-tests)
- [Reports & Evidence](#reports--evidence)
- [Architecture](#architecture)
- [Data-driven scenarios](#data-driven-scenarios)
- [AI-assisted workflow](#ai-assisted-workflow)
- [CI / GitHub Actions](#ci--github-actions)
- [Assumptions and limitations](#assumptions-and-limitations)
- [Project layout](#project-layout)

## Prerequisites

- **Python 3.11 or newer**.
- **Node.js 18+** (only required if you want to use the Playwright MCP for AI-assisted locator discovery).
- **Allure CLI 2.x** to view the Allure HTML report. Install with [`scoop install allure`](https://scoop.sh/) on Windows or `brew install allure` on macOS. JUnit XML is also produced as a fallback.

## Setup

```powershell
# Clone, then from the repo root:
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
playwright install chromium

# Create your local .env from the template:
copy .env.example .env
# (macOS/Linux: cp .env.example .env)
```

Open `.env` and fill in `SITE_EMAIL` and `SITE_PASSWORD`. You can register
a free account at <https://www.automationexercise.com/login> in under
30 seconds (any email + password), or ask the project owner for test
credentials. Optionally toggle `HEADED=true` for a visible browser.

## Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `PROFILE` | `default` | Storefront profile (`default` -> automationexercise.com). |
| `SITE_EMAIL` | _empty_ | Login email. If empty, login tests are skipped. |
| `SITE_PASSWORD` | _empty_ | Login password. Stored as `SecretStr` so it never appears in logs. |
| `HEADED` | `false` | `true` to run the browser in headed mode. |
| `SLOW_MO` | `0` | Slow each Playwright action by N ms (debugging). |
| `ACTION_TIMEOUT_MS` | `15000` | Default per-action timeout. |
| `NAVIGATION_TIMEOUT_MS` | `30000` | Default navigation timeout. |

The `.env` file is gitignored. The committed template lives in [`.env.example`](.env.example).

## Security & credentials

This project demonstrates **production-grade secret management** for test
credentials. The login user and password are committed to the repo
**encrypted** (with [SOPS][sops] + [age][age]); the plaintext `.env` never
leaves the machine that produced it.

### Files involved

| File | Purpose | Committed? |
| --- | --- | --- |
| [`.env.example`](.env.example) | Template showing every var the framework reads. | Yes |
| `.env` | Local plaintext credentials. **Never commit.** | **No** (gitignored) |
| [`.sops.yaml`](.sops.yaml) | SOPS policy: which age public keys may decrypt. | Yes |
| `secrets/credentials.sops.yaml` | The encrypted ciphertext. Safe to commit. | Yes (after encryption) |

### One-time setup (per machine)

```powershell
.\scripts\setup-secrets.ps1      # installs sops + age, generates keypair
.\scripts\encrypt-env.ps1        # .env -> secrets/credentials.sops.yaml
.\scripts\decrypt-env.ps1        # reverse: sops -> .env on a fresh checkout
```

### Pre-commit secret scanning

[`gitleaks`][gitleaks] is wired via `.pre-commit-config.yaml`:

```powershell
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

[sops]: https://github.com/getsops/sops
[age]: https://github.com/FiloSottile/age
[gitleaks]: https://github.com/gitleaks/gitleaks

## Running the tests

### Test suite overview

| File | Brief section | Assertions | What it covers |
| --- | --- | --- | --- |
| `tests/test_login.py` | 4 (Auth) | 9 | Negative login → positive login → logout, all in one browser window |
| `tests/test_e2e_purchase_flow.py` | 4.1 + 4.2 + 4.3 | 14 | Clear cart → search → add items → assert cart total → checkout summary (8 checkout assertions) |
| `tests/test_search_data_driven.py` | 4.1 (×3 scenarios) | 4 per scenario | Data-driven search: happy path / tight budget / empty result |

**Total: 35 assertions** across 5 test cases (3 data-driven scenarios count as 3 tests).
See [`test-assertions.md`](docs/test-assertions.md) for the full per-assertion breakdown.

### Recommended entry points (PowerShell)

```powershell
# Full suite in brief order (login -> e2e -> data-driven):
.\scripts\run-suite.ps1

# Watch the suite run with a visible browser:
.\scripts\run-suite.ps1 --headed=true

# Run a single test with login prepended automatically:
.\scripts\run-with-login.ps1 -Target tests/test_e2e_purchase_flow.py

# One-click demo: clean → run 5 tests (headed) → build report → open it:
.\flow_control\run-e2e.ps1

# Clear all reports only:
.\flow_control\clear-reports.ps1

# Build / view the HTML report after a run:
.\scripts\build-report.ps1     # generate reports/allure-html/
.\scripts\open-report.ps1      # serve over HTTP (http://127.0.0.1:3181)
.\scripts\view-report.ps1      # interactive allure serve
```

> `run-suite.ps1` automatically kills stale browser processes before
> starting, auto-builds the Allure HTML report when done, and pauses
> the shell so you can see the results.

### Plain pytest invocations

```powershell
pytest                                              # full suite
pytest tests/test_login.py -v                       # login standalone
pytest tests/test_e2e_purchase_flow.py -v           # e2e standalone
pytest tests/test_search_data_driven.py -v          # data-driven standalone
$env:HEADED="true"; pytest tests/test_login.py      # watch the browser
```

### Fail-fast & timeouts

- `--maxfail=3` is configured in `pytest.ini` — the suite stops after 3 failures.
- A **watchdog timer** fires 8 seconds after the last test completes and
  force-terminates the process. This prevents Playwright's session-scoped
  teardown from hanging for minutes on Windows (a known issue with
  Chromium driver shutdown on Python 3.13). All reports are written
  before the watchdog fires.

## Reports & Evidence

Every test run produces a multi-format evidence bundle. Capture is
**always-on** (pass or fail) so a green run has the same evidence as a
failure.

### What is captured per test

| Artefact | Content |
| --- | --- |
| **Video recording** (`.webm`) | One video per test, recording the whole browser context end-to-end at 1280×720. Every test has a video — pass or fail. |
| **Playwright trace** (`.zip`) | Full DOM snapshots, network, console. Open with `playwright show-trace <path>`. |
| **Screenshots** (`.png`) | Every `BasePage.screenshot(name)` call, numbered per-test (`01_login_page.png`, `02_login_rejected.png`, ...). |
| **Per-test log** (`log.txt`) | `loguru` records emitted during exactly that test. |
| `summary.json` | `{test_id, outcome, duration_seconds, started_at}` — machine-readable test ledger. |

### Allure report enhancements

| Enhancement | What it gives you |
| --- | --- |
| `environment.properties` | "Environment" widget: site, browser, headed, Python/Playwright versions, run timestamp |
| `categories.json` | "Categories" tab groups failures by root cause: selector drift, auth, network, cart, pop-up |
| `@allure.severity` | BLOCKER (login), CRITICAL (e2e), NORMAL/MINOR (data-driven) |
| `@allure.title` | Human-readable labels including parametrized values |
| `@allure.tag` | Brief section tags (`brief-section-4-1`, etc.) for filtering |

### Viewing the report

> **Important:** the Allure HTML report uses JavaScript that browsers
> block when opened via `file://`. You **must** serve it over HTTP.
> Three easy options:

```powershell
# Option 1 (recommended): run the suite — it auto-builds the report at the end
.\scripts\run-suite.ps1

# Option 2: build + serve in two steps
.\scripts\build-report.ps1        # generates reports/allure-html/
.\scripts\open-report.ps1         # serves at http://127.0.0.1:3181

# Option 3: one-shot serve from raw results (no build step)
.\scripts\view-report.ps1         # allure serve — opens browser automatically
```

Then open **http://127.0.0.1:3181** in your browser.

### Where the evidence lives

```
reports/
├── allure-results/                raw Allure JSON (one file per result)
├── allure-html/                   static HTML report (built on demand)
├── evidence/
│   └── <test_id>/<timestamp>/
│       ├── trace.zip
│       ├── video.webm
│       ├── log.txt
│       ├── screenshots/
│       └── summary.json
├── junit.xml                      CI-consumer-friendly test summary
└── pytest.log                     full pytest log
```

Everything in `reports/` is gitignored.

### Cleaning reports

```powershell
.\flow_control\clear-reports.ps1                # wipe everything (171 MB+ after a full run)
.\flow_control\clear-reports.ps1 -DryRun       # show what would go without deleting
.\flow_control\clear-reports.ps1 -KeepStorageState  # keep cached login session
```

The script also kills stale browser/pytest processes that may be holding
file handles open.

## Architecture

Layered top-down. Each layer only depends on the layer below it.

```
tests/         pytest cases (only assertions live here)
src/flows/     the 4 brief functions; orchestrate page objects
src/pages/     Page Object Model (one class per page, extends BasePage)
src/components/  reusable widgets (header, price filter, paginator, product card)
src/utils/     price parser, screenshot helper, loguru, variant picker
src/config/    pydantic-settings + site profiles
data/          YAML inputs for parameterized tests
```

Hard-line rules:

- **`Decimal` for money**, never `float`. The `PriceParser` is the single source of truth.
- **No `time.sleep`** in `src/`; only Playwright waits.
- **No assertions** in pages or components — assertions belong to tests/flows.
- **No cross-page imports** — cross-page orchestration happens in `src/flows/`.
- **Locator priority**: role → data-testid → text → CSS attr → XPath. The brief mandates XPath for `SearchResultsPage.PRODUCT_CARD_XPATH` only.
- **Credentials** never live in code — only in `.env`.

### Page Object Model

| Page | URL | Purpose |
| --- | --- | --- |
| `LoginPage` | `/login` | Fill credentials, submit, read error/success, logout |
| `SearchResultsPage` | `/products` | Submit search, collect cards via XPath, client-side price filter |
| `ProductPage` | `/product_details/<id>` | Add to cart, dismiss confirmation modal |
| `CartPage` | `/view_cart` | Sum per-line totals, delete items, proceed to checkout |
| `CheckoutPage` | `/checkout` | Verify "Review Your Order" summary, addresses, Place Order button |
| `HomePage` | `/` | Navigation entry point |

## Data-driven scenarios

Test scenarios are loaded from [`data/queries.yaml`](data/queries.yaml):

| Scenario | Query | Max Price | Limit | Expected |
| --- | --- | --- | --- | --- |
| `full_results_tshirt` | `tshirt` | Rs. 1500 | 5 | Several matches |
| `tight_budget_dress` | `dress` | Rs. 600 | 5 | Fewer matches (tight filter) |
| `empty_ok_nonsense` | `asdfqwerty12345nope` | Rs. 100 | 5 | Zero results (valid per brief) |

Adding a scenario is one YAML entry; the parametrized tests pick them up
automatically.

## AI-assisted workflow

A project-scoped AI tooling layer is committed to the repo:

| Artifact | What it does |
| --- | --- |
| [`.cursor/rules/*.mdc`](.cursor/rules/) | Five focused rule files auto-applied by Cursor based on file globs. |
| [`.cursor/commands/`](.cursor/commands/) | Slash commands `/add-page-object`, `/add-test-case`, `/debug-failing-locator`. |
| [`.cursor/mcp.json`](.cursor/mcp.json) | Project-scoped Playwright MCP (live browser) + Filesystem MCP. |
| [`docs/personas/`](docs/personas/) | Three role personas: QA Architect, Test Engineer, Code Reviewer. |
| [`AGENTS.md`](docs/AGENTS.md) | Universal AI playbook. |

Nothing here is required for the tests to run — they're augmentations.

## CI / GitHub Actions

A GitHub Actions workflow runs the full 5-test suite automatically on every
push to `main` (and on pull requests). The workflow lives in
[`.github/workflows/e2e-tests.yml`](.github/workflows/e2e-tests.yml).

| Step | What it does |
| --- | --- |
| **Login test** | Runs `test_login.py` (negative → positive → logout) |
| **E2E + data-driven** | Runs `test_e2e_purchase_flow.py` + `test_search_data_driven.py` (shared browser) |
| **Allure report** | Builds the HTML report and uploads it as a downloadable artifact |

Credentials are stored as **GitHub Secrets** (`SITE_EMAIL`, `SITE_PASSWORD`)
and injected as environment variables at runtime — they never appear in logs
or workflow files.

To view the CI results: go to the **Actions** tab on GitHub → click the
latest run → download the `test-reports` artifact.

## Assumptions and limitations

- **Login**: live credentials per `.env`. The login test has its own browser
  (negative → positive → logout). All other tests share a **single
  session-scoped browser** that logs in once and stays open — no browser
  close/reopen between tests.
- **Video**: recorded for **every test** (pass or fail) at 1280×720. This
  adds ~5–15 MB per test but guarantees the reviewer can watch the full
  user journey.
- **Site profiles**: only the `default` profile (`automationexercise.com`)
  is exercised. Adding a new profile is one entry in `src/config/settings.py`.
- **Currency**: Rs. (INR), locale-aware via `PriceParser`.
- **Anti-bot**: automationexercise.com does not present CAPTCHA/anti-bot.
- **Ad pop-ups**: auto-dismissed via `page.add_locator_handler` + network
  blocking in `conftest.py`.
- **Checkout**: we verify the "Review Your Order" summary page but do
  **not** click "Place Order" — the site's payment form is a simulator.
- **Process teardown**: a watchdog timer force-kills the process 8 seconds
  after the last test to prevent Playwright's session teardown from hanging
  (a known Windows + Python 3.13 issue).

## Project layout

```
.
├── .github/workflows/e2e-tests.yml   CI: runs all 5 tests on push to main
├── .cursor/                          Cursor project rules, commands, MCP
├── docs/personas/                    QA Architect / Test Engineer / Code Reviewer
├── src/
│   ├── config/                       pydantic-settings + region profiles
│   ├── pages/                        Page Object Model (6 pages)
│   ├── components/                   Reusable widgets (header, paginator, price filter, product card)
│   ├── flows/                        The 4 brief functions + checkout
│   └── utils/                        price_parser, screenshot, logger, variant_picker
├── tests/
│   ├── conftest.py                   Fixtures, evidence wiring, watchdog, ad-popup handler
│   ├── test_login.py                 Login flow (negative → positive → logout, 9 assertions)
│   ├── test_e2e_purchase_flow.py     Full purchase flow + checkout (14 assertions)
│   └── test_search_data_driven.py    Data-driven search (3 scenarios × 4 assertions)
├── data/queries.yaml                 Data-driven search scenarios
├── scripts/
│   ├── run-suite.ps1                 Full suite runner (brief order, pre-flight kill, auto-report)
│   ├── run-with-login.ps1            Run any test with login prepended
│   ├── build-report.ps1              Build Allure HTML report
│   ├── open-report.ps1               Serve report over HTTP
│   ├── view-report.ps1               Interactive allure serve
│   ├── setup-secrets.ps1             Install sops+age, generate keypair
│   ├── encrypt-env.ps1               .env → SOPS encrypted
│   ├── decrypt-env.ps1               SOPS → .env
│   └── make_login_evidence.py        Sanitised login evidence bundle
├── flow_control/
│   ├── run-e2e.ps1                   One-click demo: clean → run → report → open
│   └── clear-reports.ps1             Wipe all reports + stale processes
├── docs/
│   ├── AGENTS.md                     Universal AI playbook
│   ├── exercise-brief.html           Full English brief
│   ├── test-assertions.md            Per-test assertion reference (35 total)
│   ├── test-assertions.html          Same, styled HTML dashboard
│   ├── ai-workflow.md                AI-assisted workflow guide
│   └── personas/                     Role-based AI personas
├── pyproject.toml
├── pytest.ini
├── .env.example
└── .gitignore
```
