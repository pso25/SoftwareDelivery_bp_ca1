import pytest

from app import create_app


def post(client, systolic, diastolic):
    return client.post("/", data={"BP.Systolic": systolic, "BP.Diastolic": diastolic})


def test_get_index_shows_defaults_and_category(client):
    html = client.get("/").get_data(as_text=True)
    assert 'id="BP_Systolic"' in html and 'value="100"' in html
    assert 'id="BP_Diastolic"' in html and 'value="60"' in html
    assert "Ideal Blood Pressure" in html


def test_index_renders_unobtrusive_validation_attributes(client):
    html = client.get("/").get_data(as_text=True)
    assert 'data-val-range="Invalid Systolic Value"' in html
    assert 'data-val-range-min="70"' in html and 'data-val-range-max="190"' in html
    # the HTML min/max attributes get the same message (see MIGRATION.md F5)
    assert 'data-msg-max="Invalid Systolic Value"' in html
    assert 'data-msg-min="Invalid Diastolic Value"' in html
    assert "jquery.validate.unobtrusive.min.js" in html


def test_post_valid_reading_shows_category(client):
    html = post(client, 150, 95).get_data(as_text=True)
    assert "High Blood Pressure" in html


def test_post_out_of_range_shows_field_error_and_no_category(client):
    html = post(client, 200, 60).get_data(as_text=True)
    assert "Invalid Systolic Value" in html
    assert "Blood Pressure</div>" not in html.replace(" ", "").replace("\n", "")


def test_post_systolic_not_greater_than_diastolic(client):
    html = post(client, 80, 80).get_data(as_text=True)
    assert "<li>Systolic must be greater than Diastolic</li>" in html
    assert "Ideal Blood Pressure" not in html


def test_post_missing_value(client):
    html = post(client, "", 60).get_data(as_text=True)
    assert "The Systolic field is required." in html


def test_privacy_page(client):
    response = client.get("/Privacy")
    assert response.status_code == 200
    assert "Privacy Policy" in response.get_data(as_text=True)


def test_error_page_is_not_cached(client):
    response = client.get("/Error")
    assert "no-store" in response.headers["Cache-Control"]
    assert "Request ID:" in response.get_data(as_text=True)


def test_static_files_served(client):
    assert client.get("/static/css/site.css").status_code == 200
    assert "js/site.js?v=" in client.get("/").get_data(as_text=True)


def test_post_without_csrf_token_rejected():
    client = create_app("Production").test_client()
    assert post(client, 120, 80).status_code == 400


def test_unhandled_exception_shows_error_page_in_production():
    app = create_app("Production")
    app.add_url_rule("/boom", "boom", lambda: 1 / 0)
    response = app.test_client().get("/boom")
    assert response.status_code == 500
    assert "An error occurred while processing your request." in response.get_data(as_text=True)


def test_version_header_defaults_to_dev(client):
    assert client.get("/").headers["X-App-Version"] == "dev"


def test_version_header_shows_build_version(client):
    client.application.config["APP_VERSION"] = "abc123"
    assert client.get("/Privacy").headers["X-App-Version"] == "abc123"


def test_index_shows_dev_version_in_corner(client):
    assert ">Version dev</small>" in client.get("/").get_data(as_text=True)


def test_index_shows_short_commit_sha_in_corner(client):
    sha = "4df177d1234567890abcdef1234567890abcdef1"
    client.application.config["APP_VERSION"] = sha
    html = client.get("/").get_data(as_text=True)
    assert f'title="{sha}"' in html
    assert ">Version 4df177d</small>" in html


def test_privacy_page_has_no_version_label(client):
    assert 'id="app-version"' not in client.get("/Privacy").get_data(as_text=True)



@pytest.mark.parametrize("systolic, diastolic, expected_text", [
    (85, 55, "Low Blood Pressure"),
    (110, 70, "Ideal Blood Pressure"),
    (125, 82, "Pre-High Blood Pressure"),
    (145, 92, "High Blood Pressure"),
])
def test_page_shows_category_for_reading(client, systolic, diastolic, expected_text):
    response = post(client, systolic, diastolic)
    html = response.get_data(as_text=True)
    assert expected_text in html


def test_error_page_shows_request_id(client):
    response = client.get("/Error", headers={"X-Request-ID": "abc-123"})
    html = response.get_data(as_text=True)
    assert "abc-123" in html


def test_lowercase_privacy_url_is_not_found(client):
    response = client.get("/privacy")
    assert response.status_code == 404


def test_lowercase_error_url_is_not_found(client):
    response = client.get("/error")
    assert response.status_code == 404


def test_unknown_url_is_not_found(client):
    response = client.get("/does-not-exist")
    assert response.status_code == 404


# --- security headers (MIGRATION.md F8) ---

@pytest.mark.parametrize("path", ["/", "/Privacy", "/Error", "/static/css/site.css", "/missing"])
def test_security_headers_on_every_response(client, path):
    headers = client.get(path).headers
    for name, value in client.application.config["SECURITY_HEADERS"].items():
        assert headers[name] == value


def test_csp_blocks_framing_and_other_sites():
    from config import Config
    csp = Config.SECURITY_HEADERS["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp


def test_pages_are_not_cached(client):
    assert client.get("/").headers["Cache-Control"] == "no-cache, no-store, must-revalidate"


def test_static_files_stay_cacheable(client):
    assert "no-store" not in client.get("/static/css/site.css").headers.get("Cache-Control", "")


def test_error_page_keeps_its_own_cache_header(client):
    assert client.get("/Error").headers["Cache-Control"] == "no-store,no-cache"


@pytest.mark.parametrize("path", ["/", "/Privacy", "/Error"])
def test_pages_have_no_inline_styles_or_scripts(client, path):
    # the Content Security Policy would block these
    html = client.get(path).get_data(as_text=True)
    assert " style=" not in html and "<style" not in html
    assert " onclick=" not in html and "<script>" not in html


def test_production_session_cookie_is_secure():
    client = create_app("Production").test_client()
    cookie = client.get("/").headers["Set-Cookie"]
    assert "Secure" in cookie and "HttpOnly" in cookie and "SameSite=Lax" in cookie
