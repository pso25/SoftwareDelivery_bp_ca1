"""End-to-end: a user fills in the form in a real browser on the deployed site."""
import pytest
from playwright.sync_api import Page, expect

SUBMIT = "input[type=submit]"


def enter_reading(page: Page, systolic, diastolic):
    page.goto("/")
    page.fill("#BP_Systolic", str(systolic))
    page.fill("#BP_Diastolic", str(diastolic))
    page.click(SUBMIT)


@pytest.mark.parametrize("systolic, diastolic, category, advice", [
    (85, 55, "Low Blood Pressure", "See a doctor if you feel dizzy."),
    (110, 70, "Ideal Blood Pressure", "Keep up the good work!"),
    (125, 82, "Pre-High Blood Pressure", "Eat less salt and be more active."),
    (145, 92, "High Blood Pressure", "Please see a doctor."),
])
def test_reading_shows_category_and_advice(page: Page, systolic, diastolic, category, advice):
    enter_reading(page, systolic, diastolic)
    expect(page.locator("#form1")).to_contain_text(category)
    expect(page.locator("#bp-advice")).to_contain_text(advice)


def test_systolic_must_be_greater_than_diastolic(page: Page):
    # checked by the server after the form is posted
    enter_reading(page, 80, 90)
    expect(page.locator(".validation-summary-errors")).to_contain_text(
        "Systolic must be greater than Diastolic")
    expect(page.locator("#bp-advice")).to_have_count(0)


@pytest.mark.parametrize("field, value, message", [
    ("Systolic", "200", "Invalid Systolic Value"),
    ("Systolic", "60", "Invalid Systolic Value"),
    ("Diastolic", "120", "Invalid Diastolic Value"),
    ("Systolic", "", "The Systolic field is required."),
])
def test_browser_validation_stops_bad_input(page: Page, field, value, message):
    # jQuery Validation shows the same message as the server, in the browser,
    # and the form is never posted
    posts = []
    page.on("request", lambda r: posts.append(r) if r.method == "POST" else None)
    page.goto("/")
    page.fill(f"#BP_{field}", value)
    page.click(SUBMIT)
    expect(page.locator(f'[data-valmsg-for="BP.{field}"]')).to_have_text(message)
    assert posts == []
