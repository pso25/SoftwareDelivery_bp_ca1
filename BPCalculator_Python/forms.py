"""Form + validation - replaces the [Range] attributes in BloodPressure.cs, the
ModelState checks in Pages/Index.cshtml.cs and the data-val-* attributes that
Razor Tag Helpers generate for jQuery unobtrusive validation."""
from flask_wtf import FlaskForm
from wtforms import IntegerField
from wtforms.validators import InputRequired, NumberRange

from bloodpressure import BloodPressure


def _bp_field(label, minimum, maximum, error_message):
    required_message = f"The {label} field is required."
    return IntegerField(
        label,
        name=f"BP.{label}",     # same field names Razor generated (asp-for="BP.Systolic")
        id=f"BP_{label}",
        validators=[
            InputRequired(message=required_message),
            NumberRange(minimum, maximum, message=error_message),
        ],
        # client-side validation attributes, identical to the ones Razor emitted
        render_kw={
            "data-val": "true",
            "data-val-required": required_message,
            "data-val-range": error_message,
            "data-val-range-min": str(minimum),
            "data-val-range-max": str(maximum),
            # jQuery Validation also reads the HTML min/max attributes; give them
            # the ASP.NET message instead of its own default text (MIGRATION.md F5)
            "data-msg-min": error_message,
            "data-msg-max": error_message,
        },
    )


class BloodPressureForm(FlaskForm):
    systolic = _bp_field("Systolic", BloodPressure.SYSTOLIC_MIN,
                         BloodPressure.SYSTOLIC_MAX, "Invalid Systolic Value")
    diastolic = _bp_field("Diastolic", BloodPressure.DIASTOLIC_MIN,
                          BloodPressure.DIASTOLIC_MAX, "Invalid Diastolic Value")

    def validate(self, extra_validators=None):
        valid = super().validate(extra_validators)
        # extra validation (was OnPost in Index.cshtml.cs) - a model-level error,
        # shown in the validation summary rather than against a single field
        if self.systolic.data is not None and self.diastolic.data is not None \
                and not self.systolic.data > self.diastolic.data:
            self.form_errors.append("Systolic must be greater than Diastolic")
            valid = False
        return valid

    def to_model(self):
        return BloodPressure(systolic=self.systolic.data, diastolic=self.diastolic.data)
