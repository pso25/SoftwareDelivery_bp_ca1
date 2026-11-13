# BPCalculator (Python / Flask)

Python port of the ASP.NET Core Razor Pages app in `../BPCalculator`.
See [MIGRATION.md](MIGRATION.md) for a file-by-file, line-by-line comparison with the original.

## Requirements
- Python 3.10+ (developed on 3.13)

## Setup
```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate      Linux/macOS:  source .venv/bin/activate
pip install -r requirements-dev.txt
```

## Run
| Purpose | Command | URL |
|---|---|---|
| Development (debugger, DEBUG logging) | `python app.py` | http://localhost:5000 |
| Production-style server | `waitress-serve --port=5000 --call app:create_app` | http://localhost:5000 |

Environment variables:
- `APP_ENV`: `Development`, `Production` (default for `waitress-serve`) or `Testing`. Replaces `ASPNETCORE_ENVIRONMENT`.
- `SECRET_KEY`: signs the CSRF token. Set it when running more than one process/instance; otherwise a random key is generated at startup.
- `APPLICATIONINSIGHTS_CONNECTION_STRING`: when set (an app setting on prod), requests, errors, logs and a `CategoryCalculated` event go to Azure Application Insights. Not set locally or in tests, so nothing is sent (MIGRATION.md F11).

## Test
```bash
pytest -q
```

## Docker
```bash
docker build -t bpcalculator .
docker run -d -p 5000:5000 --name bpcalculator bpcalculator
```
Then open http://localhost:5000. Stop with `docker stop bpcalculator`, remove with `docker rm bpcalculator`.

## Structure
```
BPCalculator_Python/
├── app.py                 # create_app(): host + pipeline (Program.cs + Startup.cs)
├── config.py              # environments/logging (appsettings*.json, launchSettings.json)
├── bloodpressure.py       # domain model + category logic (BloodPressure.cs)
├── forms.py               # form binding + validation ([Range], ModelState, data-val-*)
├── pages.py               # route handlers (Pages/*.cshtml.cs)
├── templates/             # Jinja2 views (Pages/*.cshtml)
│   ├── base.html                  # _Layout.cshtml
│   ├── _validation_scripts.html   # _ValidationScriptsPartial.cshtml
│   ├── index.html / privacy.html / error.html
├── static/                # wwwroot/ (css, js, favicon, lib/ bootstrap + jquery)
├── tests/                 # pytest unit + integration tests (new)
├── requirements.txt       # runtime dependencies (BPCalculator.csproj)
└── requirements-dev.txt   # + pytest
```
