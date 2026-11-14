# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository layout

Blood Pressure Category Calculator (Continuous Delivery CA1). The repo holds two implementations of the same web app side by side:

- `BPCalculator/` (+ `BPCalculator.sln`): the original ASP.NET Core Razor Pages app (.NET 9). Kept **unchanged** as the reference; its `BloodPressure.Category` is still a stub that always returns `Low`.
- `BPCalculator_Python/`: the Flask 3.1 / Python 3.13 port. This is the active codebase (tests, Dockerfile). `BPCalculator_Python/MIGRATION.md` maps every .NET file/line to its Python equivalent and lists the intentional functional differences (F1–F6). Read it before changing behaviour, and keep it in sync with code changes that move line numbers or behaviour.

## Commands (run from `BPCalculator_Python/`)

```bash
python -m venv .venv && .venv\Scripts\activate     # Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt

python app.py                                       # dev server, http://localhost:5000, APP_ENV=Development
waitress-serve --port=5000 --call app:create_app    # production-style (APP_ENV defaults to Production)

pytest -q                                           # all tests
pytest tests/test_bloodpressure.py::test_category   # single test
pytest -k "csrf"                                     # by name
pytest tests/e2e --base-url http://localhost:5000   # E2E in a browser (needs `python -m playwright install chromium`; skipped without --base-url)

docker build -t bpcalculator .
docker run -d -p 5000:5000 --name bpcalculator bpcalculator
```

There is no linter or formatter configured. The .NET app runs with `dotnet run --project BPCalculator`; it has no tests.

## Architecture (Python app)

Modules use flat imports (`from config import ...`), so the app directory must be on `sys.path`; `tests/conftest.py` inserts it, and the `client` fixture builds the app with `create_app("Testing")`.

- `app.py` — `create_app(env_name)` application factory (replaces `Program.cs` + `Startup.cs`): loads config, enables `CSRFProtect`, sets `g.request_id` per request (from `X-Request-ID` or a UUID), registers a 500 handler **only when not in debug**, registers the `pages` blueprint, and provides the `static_v()` template helper that appends a content hash (`asp-append-version` equivalent).
- `config.py` — `Config` (Production) / `DevelopmentConfig` / `TestingConfig` (CSRF disabled), selected by `APP_ENV` (replaces `ASPNETCORE_ENVIRONMENT`). `SECRET_KEY` comes from the env or is random per process, so multi-instance deployments must set it.
- `bloodpressure.py` — pure domain model: `BPCategory` enum (value = display text) and `BloodPressure` dataclass with range constants and the `category` property (thresholds checked High → Pre-High → Ideal → Low; the higher reading wins).
- `forms.py` — `BloodPressureForm` (Flask-WTF). Range limits come from the `BloodPressure` constants. The cross-field rule "Systolic must be greater than Diastolic" goes into `form_errors` (rendered in the validation summary), not a field error.
- `pages.py` — blueprint with `/`, `/Privacy`, `/Error`, plus `render_error_page()` (no-cache headers), which is shared with the 500 handler.
- `templates/` (Jinja2, extend `base.html`) and `static/` (copy of the .NET `wwwroot/`, plus the new `css/version.css` and upgraded jQuery and jQuery Validation, see F9 in `MIGRATION.md`).

### Compatibility constraints to preserve

The port deliberately keeps the .NET app's external surface so existing UI tests and the client-side scripts keep working:

- Form field names/ids stay `BP.Systolic` / `BP_Systolic` and `BP.Diastolic` / `BP_Diastolic`.
- `forms.py` emits the same `data-val-*` attributes that Razor tag helpers produced; jQuery Unobtrusive Validation depends on them.
- Validation messages match ASP.NET's exactly (`Invalid Systolic Value`, `The Systolic field is required.`, etc.).
- Routes are case-sensitive: `/Privacy` and `/Error` must stay capitalised.
- A POST without a valid CSRF token returns 400 (outside the Testing config).
- The Content Security Policy in `config.py` blocks inline styles and scripts, so templates must not use them. Keep `Referrer-Policy` from being `no-referrer`, because Flask-WTF can require a `Referer` on HTTPS POSTs.

If the category thresholds change, update `bloodpressure.py` and the expected values in `tests/test_bloodpressure.py` together.
