# Migration log: ASP.NET Core (C#) → Python (Flask)

This document records every change made when rewriting `BPCalculator` (ASP.NET Core Razor Pages, .NET 9)
as `BPCalculator_Python` (Flask 3.1, Python 3.13). For each original file it gives:

- the new file(s) that replace it,
- an **old line(s) → new line(s)** table,
- a side-by-side code comparison of the significant parts,
- the reason for each change.

The original .NET project is **unchanged** and still in `../BPCalculator`, so both versions can be compared or run.

> Line numbers refer to the files as committed in this migration. Old: `BPCalculator/...`; New: `BPCalculator_Python/...`.

---

## 1. Summary

| | Old (.NET) | New (Python) |
|---|---|---|
| Language / runtime | C# 13, .NET 9 | Python 3.13 |
| Web framework | ASP.NET Core Razor Pages | Flask 3.1.3 |
| View engine | Razor (`.cshtml`) | Jinja2 (`.html`) |
| Forms / validation | Model binding + DataAnnotations (`[Range]`) | Flask-WTF 1.3.0 / WTForms 3.2.2 |
| Anti-forgery | Built-in (automatic for Razor Pages forms) | `flask_wtf.csrf.CSRFProtect` |
| Dev server | Kestrel (`dotnet run`) | Werkzeug (`python app.py`) |
| Production server | Kestrel / IIS | Waitress 3.0.2 (WSGI) |
| Environment switch | `ASPNETCORE_ENVIRONMENT` | `APP_ENV` |
| Tests | none | pytest 9.1.1 (24 tests) |
| Client-side libs | Bootstrap 4, jQuery, jQuery Validation (+ Unobtrusive) | **same files, unchanged** |

### Functional differences (read these first)

| # | Behaviour | Old | New | Why |
|---|---|---|---|---|
| F1 | **BP category** | Not implemented: always returned `new BPCategory()` = `Low` | Implemented with the standard chart (see §3.1) | The stub was the assignment's TODO. Porting a stub that always returns "Low" would not be useful. |
| F2 | URL matching | Case-insensitive (`/privacy` = `/Privacy`) | Case-sensitive: `/Privacy` and `/Error` must be capitalised as before | Flask routes are case-sensitive. All links in the app use the correct case. |
| F3 | Request ID on error page | W3C trace id (`Activity.Current.Id`) or `TraceIdentifier` | Incoming `X-Request-ID` header or a random UUID | Python has no `Activity`. Same purpose: a correlation id. |
| F4 | Unhandled errors | Not logged by the template | Logged with stack trace and request id (`app.py:37-38`) | Small improvement. `_logger` was injected in C# but never used. |
| F5 | HTML5 attributes on inputs | `type="number"` + `data-val-*` | Same, **plus** `min`, `max`, `required` | WTForms adds them automatically. jQuery Validation sets `novalidate` on the form, so users still see the same messages. |
| F6 | Anti-forgery field name | `__RequestVerificationToken` | `csrf_token` | Framework naming. A POST without a valid token still gets **HTTP 400** in both. |
| F7 | Version header and label | None | Every response has `X-App-Version` (commit SHA from the `APP_VERSION` env var, read into config at `config.py:16-17`, `dev` locally) (`app.py:59-64`). The calculator page also shows `Version <short SHA>` in its bottom-right corner, with the full SHA on hover (`app.py:66-69`, `index.html:37`) | The deploy pipeline uses the header to confirm which version is live before marking it stable or after a rollback. The label lets a person check by eye that the latest change is deployed. |
| F8 | Security headers and cookie flags | None | Every response has CSP, `X-Frame-Options`, `X-Content-Type-Options`, HSTS, `Referrer-Policy`, `Permissions-Policy` and the `Cross-Origin-*` policies (`config.py:21-37`, `app.py:71-78`). Pages also get `Cache-Control: no-cache, no-store, must-revalidate`; static files stay cacheable. The session cookie is `Secure` and `SameSite=Lax`, except in Development and Testing, which use plain HTTP (`config.py:18-20`). The version label's inline style moved to `static/css/version.css`, because the CSP blocks inline styles | Fixes the warnings from the OWASP ZAP scan of stage. Do not use `Referrer-Policy: no-referrer`: Flask-WTF can require a `Referer` on HTTPS POSTs. |
| F9 | Client-side libraries | jQuery 3.3.1, jQuery Validation 1.17.0 | jQuery 3.7.1, jQuery Validation 1.22.1 | OWASP ZAP flagged the old versions as vulnerable (High). jQuery stays on 3.x because Bootstrap 4.3.1 and jQuery Unobtrusive Validation need it. The .NET app keeps the old versions. |
| F10 | Advice per category | None | Short, plain advice for each category (`ADVICE` and the `advice` property, `bloodpressure.py:35-48`), shown under the category in its own `<p id="bp-advice">` (`index.html:32`). No advice when the reading is invalid | The CA1 new feature (user story: as a patient, I want simple advice for my category, so that I know what to do next). Kept out of the category `<div>`, so the BDD step that reads the category still works. |
| F11 | Telemetry | None | Requests, errors and logs go to Azure Application Insights through OpenTelemetry (`azure-monitor-opentelemetry`), switched on only when the `APPLICATIONINSIGHTS_CONNECTION_STRING` app setting is set (`app.py:44-47`, `83-94`). A valid submitted reading also sends a `CategoryCalculated` custom event with the category, never the readings (`pages.py:23-27`) | The brief asks for telemetry tracking in the app. App Service can't auto-instrument a custom container, so it is done in code; custom events need code anyway. Blood pressure readings are health data, so only the category is sent. Tests and local runs have no connection string and send nothing. |

Everything else (URLs, form field names/ids, validation rules and messages, page markup, CSS, JS) was kept the same on purpose. Existing UI tests that use `id="BP_Systolic"` or `name="BP.Systolic"` will still work.

---

## 2. File mapping

| Old file (`BPCalculator/`) | New file (`BPCalculator_Python/`) | Status |
|---|---|---|
| `../BPCalculator.sln` | — | Removed: no solution files in Python |
| `BPCalculator.csproj` | `requirements.txt`, `requirements-dev.txt` | Rewritten |
| `Program.cs` | `app.py` (lines 18-20, 97-99) | Rewritten |
| `Startup.cs` | `app.py` (lines 21-57) | Rewritten |
| `BloodPressure.cs` | `bloodpressure.py` (domain), `forms.py` (validation) | Rewritten + **split** |
| `appsettings.json` | `config.py` → `Config` | Rewritten |
| `appsettings.Development.json` | `config.py` → `DevelopmentConfig` | Rewritten |
| `Properties/launchSettings.json` | `app.py:97-99`, `config.py:60-62` | Rewritten |
| `Pages/_ViewImports.cshtml` | — | Removed: Jinja2 needs no imports / tag-helper registration |
| `Pages/_ViewStart.cshtml` | `{% extends "base.html" %}` at the top of each template | Replaced |
| `Pages/Index.cshtml.cs` | `pages.py:13-28`, `forms.py:38-49` | Rewritten |
| `Pages/Index.cshtml` | `templates/index.html` | Rewritten |
| `Pages/Privacy.cshtml.cs` | `pages.py:31-34` | Rewritten |
| `Pages/Privacy.cshtml` | `templates/privacy.html` | Rewritten |
| `Pages/Error.cshtml.cs` | `pages.py:37-49`, `app.py:27-39` | Rewritten |
| `Pages/Error.cshtml` | `templates/error.html` | Rewritten |
| `Pages/Shared/_Layout.cshtml` | `templates/base.html` | Rewritten |
| `Pages/Shared/_ValidationScriptsPartial.cshtml` | `templates/_validation_scripts.html` | Rewritten |
| `wwwroot/**` (css, js, favicon, lib) | `static/**` | **Copied unchanged** (byte-identical), except the upgraded jQuery and jQuery Validation (F9); `static/css/version.css` is new (F8) |
| — | `tests/conftest.py`, `tests/test_bloodpressure.py`, `tests/test_app.py` | **New** |
| — | `README.md`, `MIGRATION.md`, `.gitignore` | **New** |

---

## 3. File-by-file comparison

### 3.1 `BloodPressure.cs` → `bloodpressure.py` + `forms.py`

The C# class mixed **domain logic** (values, category) with **validation** (`[Range]` attributes that drive model binding and client-side validation). Python has no attribute-driven validation, so the class is split:
- `bloodpressure.py`: the plain domain model (easy to unit test)
- `forms.py`: validation (see §3.4)

| Old lines | Old code | New lines | New code | Change |
|---|---|---|---|---|
| 1-3 | `using System; ...DataAnnotations; ...Diagnostics;` | 2-3 | `from dataclasses import dataclass` / `from enum import Enum` | Imports. `System.Diagnostics` was unused and dropped. |
| 5-6, 40 | `namespace BPCalculator { ... }` | — | (module = namespace) | Python modules act as namespaces |
| 7-14 | `enum BPCategory` with `[Display(Name=...)]` | 6-11 | `class BPCategory(Enum)` with string values | Display name is now the enum **value** |
| 16-17 | `public class BloodPressure` | 14-15 | `@dataclass class BloodPressure` | Dataclass generates `__init__`/`__eq__`/`__repr__` |
| 18-21 | `public const int SystolicMin = 70;` ... | 16-19 | `SYSTOLIC_MIN = 70` ... | PEP 8 constant names; same values |
| 23 | `[Range(SystolicMin, SystolicMax, ErrorMessage = "Invalid Systolic Value")]` | `forms.py` 19, 33-34 | `NumberRange(minimum, maximum, message=...)` | Validation moved to the form |
| 24 | `public int Systolic { get; set; } // mmHG` | 21 | `systolic: int  # mmHg` | Property → dataclass field |
| 26 | `[Range(DiastolicMin, ...)]` | `forms.py` 19, 35-36 | `NumberRange(...)` | Moved to the form |
| 27 | `public int Diastolic { get; set; }` | 22 | `diastolic: int  # mmHg` | Property → dataclass field |
| 29-38 | `Category` getter returning `new BPCategory()` | 24-33 | `@property def category(...)` with real logic | **F1: implemented** |
| — | — | 35-48 | `@property def advice(...)` + `ADVICE` text per category | **New** (F10) |

**Side by side: enum**
```csharp
// OLD  BloodPressure.cs:8-14
public enum BPCategory
{
    [Display(Name="Low Blood Pressure")] Low,
    [Display(Name="Ideal Blood Pressure")]  Ideal,
    [Display(Name="Pre-High Blood Pressure")] PreHigh,
    [Display(Name ="High Blood Pressure")]  High
};
```
```python
# NEW  bloodpressure.py:7-11
class BPCategory(Enum):
    LOW = "Low Blood Pressure"
    IDEAL = "Ideal Blood Pressure"
    PRE_HIGH = "Pre-High Blood Pressure"
    HIGH = "High Blood Pressure"
```

**Side by side: category (functional change F1)**
```csharp
// OLD  BloodPressure.cs:30-38
public BPCategory Category
{
    get
    {
        // implement as part of project
        //throw new NotImplementedException("not implemented yet");
        return new BPCategory();                       // replace this  -> always Low
    }
}
```
```python
# NEW  bloodpressure.py:24-33
@property
def category(self) -> BPCategory:
    if self.systolic >= 140 or self.diastolic >= 90:
        return BPCategory.HIGH
    if self.systolic >= 120 or self.diastolic >= 80:
        return BPCategory.PRE_HIGH
    if self.systolic >= 90 or self.diastolic >= 60:
        return BPCategory.IDEAL
    return BPCategory.LOW
```
Rules, checked from highest to lowest so that the **higher** of the two readings decides the category:

| Category | Systolic | | Diastolic |
|---|---|---|---|
| High | ≥ 140 | or | ≥ 90 |
| Pre-High | 120-139 | or | 80-89 |
| Ideal | 90-119 | or | 60-79 |
| Low | < 90 | and | < 60 |

> If your assignment brief uses different thresholds, change only `bloodpressure.py:27-33` and the expected values in `tests/test_bloodpressure.py`.

---

### 3.2 `Program.cs` → `app.py`

| Old lines | Old code | New lines | New code | Change |
|---|---|---|---|---|
| 1-8 | `using ...` | 3-13 | `import ...` | Imports |
| 14-17 | `static void Main(string[] args) { CreateHostBuilder(args).Build().Run(); }` | 97-99 | `if __name__ == "__main__": create_app(...).run(host="localhost", port=5000)` | Entry point |
| 19-24 | `Host.CreateDefaultBuilder(args).ConfigureWebHostDefaults(... UseStartup<Startup>())` | 18-20 | `def create_app(env_name=None): app = Flask(__name__); app.config.from_object(...)` | Host builder → **application factory** |
| 27 | `//` | — | — | Stray comment removed |

```csharp
// OLD  Program.cs:14-24
public static void Main(string[] args)
{
    CreateHostBuilder(args).Build().Run();
}
public static IHostBuilder CreateHostBuilder(string[] args) =>
    Host.CreateDefaultBuilder(args)
        .ConfigureWebHostDefaults(webBuilder => { webBuilder.UseStartup<Startup>(); });
```
```python
# NEW  app.py:18-20 and 97-99
def create_app(env_name=None):
    app = Flask(__name__)
    app.config.from_object(get_config(env_name))
    ...
if __name__ == "__main__":
    # launchSettings.json profile "BPCalculator": http://localhost:5000, Development
    create_app(os.environ.get("APP_ENV", "Development")).run(host="localhost", port=5000)
```
For production, `waitress-serve --call app:create_app` calls the same factory, just as Kestrel runs the built host.

---

### 3.3 `Startup.cs` → `app.py`

| Old lines | Old code | New lines | New code | Change |
|---|---|---|---|---|
| 15-20 | `Startup(IConfiguration configuration)` + `Configuration` property | 20 | `app.config.from_object(...)` | Config is available as `app.config` |
| — (implicit in `CreateDefaultBuilder`) | Logging set up from `appsettings.json` | 21 | `logging.basicConfig(level=app.config["LOG_LEVEL"])` | Explicit logging setup |
| 23-26 | `services.AddRazorPages();` | 23-24 | `csrf.init_app(app)` | Razor Pages enables anti-forgery automatically; Flask needs it added |
| 31-34 | `if (env.IsDevelopment()) app.UseDeveloperExceptionPage();` | 32-34 | `if not app.debug:` (Werkzeug debugger handles Development) | Same behaviour |
| 35-38 | `else app.UseExceptionHandler("/Error");` | 35-39 | `@app.errorhandler(InternalServerError)` → `render_error_page(500)` | Same behaviour, plus logging (F4) |
| — (from `ErrorModel.OnGet`) | `Activity.Current?.Id ?? HttpContext.TraceIdentifier` | 27-30 | `before_request` sets `g.request_id` | F3 |
| 40 | `app.UseStaticFiles();` | — | Built into Flask (`/static/...`) | No code needed |
| 42 | `app.UseRouting();` | — | Built into Flask | No code needed |
| 44 | `app.UseAuthorization();` | — | — | **Removed**: no authorization was configured, so it did nothing |
| 46-49 | `endpoints.MapRazorPages();` | 41-42 | `app.register_blueprint(pages)` | Routes registered from `pages.py` |
| (`_Layout.cshtml:46` `asp-append-version="true"`) | Tag helper appends `?v=<hash>` | 49-57 | `static_v()` context processor | Same cache-busting behaviour |
| — | — | 59-64 | `after_request` adds `X-App-Version` | **New** (F7) |
| — | — | 66-69 | `context_processor` passes `app_version` to templates | **New** (F7) |
| — | — | 44-47, 83-94 | `enable_telemetry(app)` when `APPLICATIONINSIGHTS_CONNECTION_STRING` is set | **New** (F11) |
| — | — | 71-78 | `after_request` adds the security headers and `Cache-Control: no-cache, no-store, must-revalidate` on pages | **New** (F8) |

```csharp
// OLD  Startup.cs:29-50
public void Configure(IApplicationBuilder app, IWebHostEnvironment env)
{
    if (env.IsDevelopment()) { app.UseDeveloperExceptionPage(); }
    else { app.UseExceptionHandler("/Error"); }
    app.UseStaticFiles();
    app.UseRouting();
    app.UseAuthorization();
    app.UseEndpoints(endpoints => { endpoints.MapRazorPages(); });
}
```
```python
# NEW  app.py:26-42
@app.before_request
def assign_request_id():
    g.request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex

if not app.debug:
    @app.errorhandler(InternalServerError)
    def handle_error(e):
        app.logger.error("Unhandled exception, request id %s", g.get("request_id"),
                         exc_info=e.original_exception)
        return render_error_page(500)

app.register_blueprint(pages)
```
Small difference: `UseExceptionHandler` re-runs the `/Error` page and keeps status 500. The Flask handler renders the same template directly with status 500. Users see the same result.

---

### 3.4 `Pages/Index.cshtml.cs` → `pages.py` + `forms.py`

| Old lines | Old code | New lines | New code | Change |
|---|---|---|---|---|
| 8 | `class BloodPressureModel : PageModel` | `pages.py` 13-15 | `@pages.route("/", methods=["GET","POST"]) def index():` | Class with handlers → one view function |
| 10-11 | `[BindProperty] public BloodPressure BP` | `pages.py` 17; `forms.py` 15-16 | `BloodPressureForm()` binds `request.form`; fields named `BP.Systolic` / `BP.Diastolic` | Model binding → WTForms. **Field names kept the same.** |
| 14-17 | `OnGet() { BP = new BloodPressure() { Systolic = 100, Diastolic = 60 }; }` | `pages.py` 19-21 | `form = BloodPressureForm(systolic=100, diastolic=60)` | Same defaults |
| 20 | `OnPost()` | `pages.py` 16-18 | `if request.method == "POST": ... form.validate()` | Handler split → `if` on method |
| (implicit) | `[Range]` checked during binding → `ModelState` | `forms.py` 11-29, 39 | `InputRequired` + `NumberRange`, `super().validate()` | Explicit validators |
| 22-26 | `if (!(BP.Systolic > BP.Diastolic)) ModelState.AddModelError("", "...")` | `forms.py` 38-46 | `validate()` override appends to `self.form_errors` | Same check and message. Model-level error ("" key) → `form_errors`. |
| 27 | `return Page();` | `pages.py` 22, 28 | `bp = form.to_model() if is_valid else None; return render_template(...)` | Same page is re-rendered |
| — | — | `pages.py` 23-27 | `logger.info(...)` with `microsoft.custom_event.name = CategoryCalculated` | **New** (F11) |

```csharp
// OLD  Pages/Index.cshtml.cs:10-28
[BindProperty]                              // bound on POST
public BloodPressure BP { get; set; }

public void OnGet()
{
    BP = new BloodPressure() { Systolic = 100, Diastolic = 60 };
}

public IActionResult OnPost()
{
    if (!(BP.Systolic > BP.Diastolic))
    {
        ModelState.AddModelError("", "Systolic must be greater than Diastolic");
    }
    return Page();
}
```
```python
# NEW  pages.py:14-28 (without the F11 event, lines 23-27)
@pages.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        form = BloodPressureForm()                  # bound from the posted form
        is_valid = form.validate()
    else:
        form = BloodPressureForm(systolic=100, diastolic=60)   # setup initial data
        is_valid = True
    bp = form.to_model() if is_valid else None
    return render_template("index.html", form=form, bp=bp)
```
```python
# NEW  forms.py:38-46
def validate(self, extra_validators=None):
    valid = super().validate(extra_validators)
    if self.systolic.data is not None and self.diastolic.data is not None \
            and not self.systolic.data > self.diastolic.data:
        self.form_errors.append("Systolic must be greater than Diastolic")
        valid = False
    return valid
```
Validation messages are identical to the original:

| Rule | Message (old and new) |
|---|---|
| Systolic outside 70-190 | `Invalid Systolic Value` |
| Diastolic outside 40-100 | `Invalid Diastolic Value` |
| Field empty | `The Systolic field is required.` / `The Diastolic field is required.` (ASP.NET Core's default text) |
| Systolic ≤ Diastolic | `Systolic must be greater than Diastolic` |

`forms.py:22-28` writes out the `data-val-*` attributes that Razor's `asp-for` tag helper generated automatically, so the **same** jQuery Unobtrusive Validation scripts work in the browser without changes.

---

### 3.5 `Pages/Index.cshtml` → `templates/index.html`

| Old lines | Old code | New lines | New code | Change |
|---|---|---|---|---|
| 1-2 | `@page` / `@model BPCalculator.Pages.BloodPressureModel` | 1 | `{% extends "base.html" %}` | Routing is in `pages.py`; the layout is inherited explicitly |
| 4-6 | `ViewData["Title"] = "BP Category Calculator";` | 3 | `{% block title %}BP Category Calculator{% endblock %}` | ViewData → template block |
| 9-13 | heading, row, `<form method="post" id="form1">` | 6-10 | identical HTML | Unchanged |
| (auto-injected by Razor) | hidden `__RequestVerificationToken` | 11 | `{{ form.csrf_token }}` | CSRF token rendered explicitly (F6) |
| 14 | `<div asp-validation-summary="ModelOnly" class="text-danger"></div>` | 12-14 | `<div class="text-danger validation-summary-...">` + loop over `form.form_errors` | Tag helper → explicit markup with the same CSS classes |
| 16 | `<label asp-for="BP.Systolic" class="control-label"></label>` | 16 | `{{ form.systolic.label(class="control-label") }}` | Renders `<label for="BP_Systolic">Systolic</label>` |
| 17 | `<input asp-for="BP.Systolic" class="form-control"/>` | 17 | `{{ form.systolic(class="form-control") }}` | Same `id`, `name`, `type`, `data-val-*` (F5) |
| 18 | `<span asp-validation-for="BP.Systolic" class="text-danger"></span>` | 18 | `<span class="text-danger" data-valmsg-for=... data-valmsg-replace="true">{{ first error }}</span>` | Tag helper → explicit markup |
| 21-23 | Diastolic label/input/span | 21-23 | Same pattern | As above |
| 25-27 | Submit button | 25-27 | identical | Unchanged |
| 28 | `@if (ViewData.ModelState.IsValid)` | 28 | `{% if bp %}` | `bp` is only set when the form is valid |
| 31 | `@Html.DisplayFor(model => model.BP.Category, ...)` | 30 | `{{ bp.category.value }}` | Shows the display name, e.g. "Ideal Blood Pressure" |
| — | — | 32 | `<p id="bp-advice">{{ bp.advice }}</p>` | **New** (F10) |
| — | — | 37 | `<small id="app-version">Version {{ app_version[:7] }}</small>`, fixed to the bottom-right corner | **New** (F7) |
| 38-40 | `@section Scripts { await Html.RenderPartialAsync("_ValidationScriptsPartial"); }` | 40-42 | `{% block scripts %}{% include "_validation_scripts.html" %}{% endblock %}` | Section/partial → block/include |

```html
<!-- OLD  Index.cshtml:14-18, 28-33 -->
<div asp-validation-summary="ModelOnly" class="text-danger"></div>
<div class="form-group">
    <label asp-for="BP.Systolic" class="control-label"></label>
    <input asp-for="BP.Systolic" class="form-control"/>
    <span asp-validation-for="BP.Systolic" class="text-danger"></span>
</div>
@if (ViewData.ModelState.IsValid)
{
    <div class="form-group">
        @Html.DisplayFor(model => model.BP.Category, new { htmlAttributes = new { @class = "form-control" } })
    </div>
}
```
```html
<!-- NEW  index.html:12-18, 28-32 -->
<div class="text-danger {{ 'validation-summary-errors' if form.form_errors else 'validation-summary-valid' }}">
    <ul>{% for message in form.form_errors %}<li>{{ message }}</li>{% endfor %}</ul>
</div>
<div class="form-group">
    {{ form.systolic.label(class="control-label") }}
    {{ form.systolic(class="form-control") }}
    <span class="text-danger" data-valmsg-for="{{ form.systolic.name }}" data-valmsg-replace="true">{{ form.systolic.errors[0] if form.systolic.errors }}</span>
</div>
{% if bp %}
    <div class="form-group">
        {{ bp.category.value }}
    </div>
{% endif %}
```
Rendered HTML (checked against the running server): `<input class="form-control" data-val="true" data-val-range="Invalid Systolic Value" data-val-range-max="190" data-val-range-min="70" data-val-required="The Systolic field is required." id="BP_Systolic" max="190" min="70" name="BP.Systolic" required type="number" value="100">`

---

### 3.6 `Pages/Shared/_Layout.cshtml` → `templates/base.html`

The markup is identical line for line, apart from the new `version.css` link at line 9 (F8), so from there on the new file's line numbers are one higher than those below. Only Razor-specific syntax changed:

| Line(s) (old = new) | Old | New |
|---|---|---|
| 6 | `<title>@ViewData["Title"] - BPCalculator</title>` | `<title>{% block title %}{% endblock %} - BPCalculator</title>` |
| 7-8 | `href="~/lib/bootstrap/...css"`, `href="~/css/site.css"` | `href="{{ url_for('static', filename='...') }}"` |
| 14, 22 | `asp-area="" asp-page="/Index"` | `href="{{ url_for('pages.index') }}"` |
| 25, 40 | `asp-area="" asp-page="/Privacy"` | `href="{{ url_for('pages.privacy') }}"` |
| 34 | `@RenderBody()` | `{% block content %}{% endblock %}` |
| 44-45 | `src="~/lib/..."` | `src="{{ url_for('static', filename='lib/...') }}"` |
| 46 | `src="~/js/site.js" asp-append-version="true"` | `src="{{ static_v('js/site.js') }}"` (helper in `app.py:49-57`) |
| 48 | `@RenderSection("Scripts", required: false)` | `{% block scripts %}{% endblock %}` |

### 3.7 `Pages/Shared/_ValidationScriptsPartial.cshtml` → `templates/_validation_scripts.html`

| Line | Old | New |
|---|---|---|
| 1 | `<script src="~/lib/jquery-validation/dist/jquery.validate.min.js"></script>` | `<script src="{{ url_for('static', filename='lib/jquery-validation/dist/jquery.validate.min.js') }}"></script>` |
| 2 | `<script src="~/lib/jquery-validation-unobtrusive/jquery.validate.unobtrusive.min.js"></script>` | `<script src="{{ url_for('static', filename='lib/jquery-validation-unobtrusive/jquery.validate.unobtrusive.min.js') }}"></script>` |

### 3.8 `Pages/_ViewStart.cshtml` and `Pages/_ViewImports.cshtml`

| Old | New | Reason |
|---|---|---|
| `_ViewStart.cshtml:2` `Layout = "_Layout";` | Line 1 of each page template: `{% extends "base.html" %}` | Jinja2 has no global default layout; each page names its layout |
| `_ViewImports.cshtml:1-3` `@using`, `@namespace`, `@addTagHelper` | — (deleted) | Jinja2 needs no imports or tag-helper registration |

### 3.9 `Pages/Privacy.cshtml(.cs)` → `pages.py:31-34` + `templates/privacy.html`

| Old lines | Old code | New lines | New code | Change |
|---|---|---|---|---|
| `.cs` 11 | `class PrivacyModel : PageModel` | `pages.py` 32-33 | `@pages.route("/Privacy") def privacy():` | Class → function. URL kept. |
| `.cs` 13-18 | `ILogger<PrivacyModel> _logger` injected | — | — | **Removed**: never used |
| `.cs` 20-22 | `public void OnGet() { }` | `pages.py` 34 | `return render_template("privacy.html")` | — |
| `.cshtml` 1-5 | `@page`, `@model`, `ViewData["Title"] = "Privacy Policy"` | `privacy.html` 1-2 | `{% extends %}`, `{% block title %}Privacy Policy{% endblock %}` | — |
| `.cshtml` 6 | `<h1>@ViewData["Title"]</h1>` | `privacy.html` 5 | `<h1>Privacy Policy</h1>` | Jinja2 child blocks can't read a sibling block's value, so the text is written out |
| `.cshtml` 8 | `<p>Use this page ...</p>` | `privacy.html` 7 | identical | Unchanged |

### 3.10 `Pages/Error.cshtml(.cs)` → `pages.py:37-49`, `app.py:27-39` + `templates/error.html`

| Old lines | Old code | New lines | New code | Change |
|---|---|---|---|---|
| `.cs` 12 | `[ResponseCache(Duration = 0, Location = None, NoStore = true)]` | `pages.py` 46-48 | `Cache-Control: no-store,no-cache` + `Pragma: no-cache` | Attribute → explicit headers (same headers ASP.NET emits) |
| `.cs` 13 | `class ErrorModel : PageModel` | `pages.py` 38-40 | `@pages.route("/Error") def error():` | URL kept |
| `.cs` 15, 17 | `RequestId`, `ShowRequestId => !IsNullOrEmpty(RequestId)` | `error.html` 8 | `{% if request_id %}` | Computed property → template condition |
| `.cs` 19-24 | `ILogger<ErrorModel> _logger` (unused) | `app.py` 37-38 | `app.logger.error(...)` | Logger is now actually used (F4) |
| `.cs` 26-29 | `OnGet() { RequestId = Activity.Current?.Id ?? HttpContext.TraceIdentifier; }` | `app.py` 27-30 | `g.request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex` | F3 |
| `.cshtml` 11-16 | `@if (Model.ShowRequestId) { ... @Model.RequestId ... }` | `error.html` 8-12 | `{% if request_id %} ... {{ request_id }} ... {% endif %}` | Syntax only |
| `.cshtml` 25 | "...setting the **ASPNETCORE_ENVIRONMENT** environment variable..." | `error.html` 21 | "...setting the **APP_ENV** environment variable..." | Text updated for the new env variable |

### 3.11 `appsettings*.json` + `Properties/launchSettings.json` → `config.py` + `app.py`

| Old file:line | Old setting | New file:line | New setting |
|---|---|---|---|
| `appsettings.json:4` | `"Default": "Information"` | `config.py:11` | `LOG_LEVEL = "INFO"` |
| `appsettings.json:5-6` | `"Microsoft": "Warning"`, `"Microsoft.Hosting.Lifetime": "Information"` | — | Not needed: framework-specific categories |
| `appsettings.json:9` | `"AllowedHosts": "*"` | — | Flask accepts all hosts by default (same behaviour) |
| `appsettings.Development.json:4` | `"Default": "Debug"` | `config.py:43` | `LOG_LEVEL = "DEBUG"` |
| `launchSettings.json:22` | `"applicationUrl": "http://localhost:5000"` | `app.py:99` | `.run(host="localhost", port=5000)` |
| `launchSettings.json:24` | `"ASPNETCORE_ENVIRONMENT": "Development"` | `app.py:99`, `config.py:60-62` | `APP_ENV` (default `Development` for `python app.py`, `Production` otherwise) |
| `launchSettings.json:2-16` | IIS Express profile (port 53135) | — | **Removed**: IIS Express is Windows/.NET only |
| (implicit Data Protection keys) | auto-generated anti-forgery key | `config.py:12-15` | `SECRET_KEY` from env, or random per process |
| — | — | `config.py:16-17` | **New** `APP_VERSION` from env, `dev` if not set (F7) |
| — | — | `config.py:18-37` | **New** session cookie flags and `SECURITY_HEADERS` (F8) |
| — | — | `config.py:47-50` | **New** `TestingConfig` (CSRF off for tests) |

### 3.12 `BPCalculator.csproj` + `BPCalculator.sln` → `requirements*.txt`

| Old line | Old | New | Change |
|---|---|---|---|
| `.csproj` 1 | `<Project Sdk="Microsoft.NET.Sdk.Web">` | `requirements.txt` 1: `Flask==3.1.3` | Web SDK → web framework package |
| `.csproj` 4 | `<TargetFramework>net9.0</TargetFramework>` | README: Python 3.10+ | — |
| `.csproj` 7-12 | `Remove="Data\**"` | — | Removed: no `Data` folder exists |
| `.csproj` 16 | `Microsoft.VisualStudio.Web.CodeGeneration.Design 2.0.3` | — | **Removed**: VS scaffolding tool, not needed at runtime |
| `.csproj` 19 | `DotNetCliToolReference ...CodeGeneration.Tools 2.0.3` | — | **Removed**: obsolete .NET Core 2.x tooling |
| — | — | `requirements.txt` 2-4: `Flask-WTF`, `WTForms`, `waitress` | **New**: forms/CSRF + production server |
| — | — | `requirements.txt` 5: `azure-monitor-opentelemetry` | **New**: telemetry to Application Insights (F11) |
| — | — | `requirements-dev.txt`: `pytest==9.1.1` | **New**: test runner |
| `BPCalculator.sln` (whole file) | VS solution | — | Not used in Python |

### 3.13 `wwwroot/` → `static/`

`lib/jquery` and `lib/jquery-validation` were later upgraded (F9), so they no longer match `wwwroot/`. Otherwise copied **unchanged** (`css/site.css`, `js/site.js`, `favicon.ico`, `lib/bootstrap`, `lib/jquery`, `lib/jquery-validation`, `lib/jquery-validation-unobtrusive`, including their licence files). Only the folder name changed, because Flask serves `static/` at `/static/...`.

| Old URL | New URL |
|---|---|
| `/css/site.css` | `/static/css/site.css` |
| `/lib/bootstrap/dist/css/bootstrap.min.css` | `/static/lib/bootstrap/dist/css/bootstrap.min.css` |
| `/js/site.js?v=<hash>` | `/static/js/site.js?v=<hash>` |

---

## 4. New files (no .NET equivalent)

| File | Purpose |
|---|---|
| `tests/conftest.py` | pytest fixture: creates the app with `TestingConfig` and a test client |
| `tests/test_bloodpressure.py` | 18 unit tests: every category boundary + display names + advice per category (F10) |
| `tests/test_telemetry.py` | 4 tests: telemetry off without the connection string and on with it, the `CategoryCalculated` event holds the category but not the readings, no event on page open or for an invalid reading (F11) |
| `tests/test_app.py` | 11 integration tests: GET defaults, `data-val-*` attributes, valid POST, out-of-range, Systolic ≤ Diastolic, missing value, `/Privacy`, `/Error` no-cache headers, static files + version hash, **CSRF rejection (400)**, **unhandled exception → error page (500)** |
| `README.md` | Setup, run and test instructions |
| `MIGRATION.md` | This document |
| `.gitignore` | Ignores `.venv/`, `__pycache__/`, `.pytest_cache/` |
| `Dockerfile` | Single-stage image: python:3.13-slim, installs `requirements.txt`, runs Waitress on port 5000. The .NET project had no Dockerfile. |
| `.dockerignore` | Keeps `.venv`, caches, tests, docs and git data out of the image |

## 5. Verification performed

- `pytest -q` → **24 passed**.
- Ran under Waitress in Production mode and checked with `curl`: GET `/` → form with defaults; POST `130/85` with the CSRF token and cookie → "Pre-High Blood Pressure"; `/Privacy` → 200.
- The .NET SDK is not installed on this machine, so the original app's rendered HTML could not be diffed directly. Field names, ids and `data-val-*` attributes were matched against what ASP.NET Core tag helpers generate for this model.
