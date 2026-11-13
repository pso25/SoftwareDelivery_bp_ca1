"""Application entry point - replaces Program.cs (host) and Startup.cs (services
and request pipeline)."""
import hashlib
import logging
import os
import uuid

from flask import Flask, g, request, url_for
from flask_wtf.csrf import CSRFProtect
from werkzeug.exceptions import InternalServerError

from config import get_config
from pages import pages, render_error_page

csrf = CSRFProtect()


def create_app(env_name=None):
    app = Flask(__name__)
    app.config.from_object(get_config(env_name))
    logging.basicConfig(level=app.config["LOG_LEVEL"])

    # ConfigureServices: services.AddRazorPages() + automatic anti-forgery validation
    csrf.init_app(app)

    # Configure: request pipeline
    @app.before_request
    def assign_request_id():
        # equivalent of Activity.Current?.Id ?? HttpContext.TraceIdentifier
        g.request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex

    if not app.debug:
        # app.UseExceptionHandler("/Error"); in Development (DEBUG) Flask's debugger
        # replaces app.UseDeveloperExceptionPage()
        @app.errorhandler(InternalServerError)
        def handle_error(e):
            app.logger.error("Unhandled exception, request id %s", g.get("request_id"),
                             exc_info=e.original_exception)
            return render_error_page(500)

    # endpoints.MapRazorPages()  (app.UseStaticFiles() is built into Flask: /static)
    app.register_blueprint(pages)

    # telemetry to Azure Application Insights, only when its connection string is set
    # (an app setting on prod), so tests and local runs send nothing (MIGRATION.md F11)
    if os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING"):
        enable_telemetry(app)

    # asp-append-version="true": add a content hash so browsers refetch changed files
    @app.context_processor
    def versioned_static():
        def static_v(filename):
            path = os.path.join(app.static_folder, filename)
            with open(path, "rb") as f:
                digest = hashlib.sha256(f.read()).hexdigest()[:16]
            return url_for("static", filename=filename, v=digest)
        return {"static_v": static_v}

    # the deploy health check uses this header to tell when the new version is live
    # (not in the .NET app, see MIGRATION.md F7)
    @app.after_request
    def add_version_header(response):
        response.headers["X-App-Version"] = app.config["APP_VERSION"]
        return response

    # the same version, shown in a corner of the calculator page
    @app.context_processor
    def version_context():
        return {"app_version": app.config["APP_VERSION"]}

    # browser security protections on every response (see MIGRATION.md F8)
    @app.after_request
    def add_security_headers(response):
        response.headers.update(app.config["SECURITY_HEADERS"])
        # pages can show a reading, so keep them out of caches; static files stay cacheable
        if request.endpoint != "static":
            response.headers.setdefault("Cache-Control", "no-cache, no-store, must-revalidate")
        return response

    return app


def enable_telemetry(app):
    # imported here, so the app starts without them when telemetry is off
    from azure.monitor.opentelemetry import configure_azure_monitor
    from opentelemetry.instrumentation.flask import FlaskInstrumentor

    # the exporter's own INFO logs would be sent as telemetry too, and so on forever
    logging.getLogger("azure").setLevel(logging.WARNING)
    # sends logs, errors and dependencies; requests are tracked on this app below
    # sampling_ratio=1.0 keeps every request (the default rate limit drops the first ones)
    configure_azure_monitor(sampling_ratio=1.0,
                            instrumentation_options={"flask": {"enabled": False}})
    FlaskInstrumentor().instrument_app(app)


if __name__ == "__main__":
    # launchSettings.json profile "BPCalculator": http://localhost:5000, Development
    create_app(os.environ.get("APP_ENV", "Development")).run(host="localhost", port=5000)
