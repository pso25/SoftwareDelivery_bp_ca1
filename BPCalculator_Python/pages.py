"""Page handlers - replaces the PageModel classes in Pages/*.cshtml.cs.
Routes keep the Razor Pages URLs: /, /Privacy and /Error."""
import logging

from flask import Blueprint, g, make_response, render_template, request

from forms import BloodPressureForm

pages = Blueprint("pages", __name__)
logger = logging.getLogger(__name__)


# Index - was BloodPressureModel (Pages/Index.cshtml.cs)
@pages.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        form = BloodPressureForm()                  # bound from the posted form
        is_valid = form.validate()
    else:
        form = BloodPressureForm(systolic=100, diastolic=60)   # setup initial data
        is_valid = True
    bp = form.to_model() if is_valid else None
    if request.method == "POST" and bp:
        # custom event in App Insights: the category only, never the readings (health data)
        logger.info("Category calculated: %s", bp.category.name, extra={
            "microsoft.custom_event.name": "CategoryCalculated",
            "category": bp.category.name})
    return render_template("index.html", form=form, bp=bp)


# Privacy - was PrivacyModel (Pages/Privacy.cshtml.cs)
@pages.route("/Privacy")
def privacy():
    return render_template("privacy.html")


# Error - was ErrorModel (Pages/Error.cshtml.cs)
@pages.route("/Error")
def error():
    return render_error_page(200)


def render_error_page(status_code):
    response = make_response(
        render_template("error.html", request_id=g.get("request_id")), status_code)
    # [ResponseCache(Duration = 0, Location = ResponseCacheLocation.None, NoStore = true)]
    response.headers["Cache-Control"] = "no-store,no-cache"
    response.headers["Pragma"] = "no-cache"
    return response
