from flask import Blueprint, render_template
import core.utils.web_utils as web_utils

main_bp = Blueprint('main', __name__)


@main_bp.route("/")
def index():
    payment_data_from_files = web_utils.get_payment_data()
    app_settings = web_utils.get_app_settings()
    user_grouped_data = {}
    for filename, owners_data in payment_data_from_files.items():
        for owner_name, methods_data in owners_data.items():
            if owner_name not in user_grouped_data:
                user_grouped_data[owner_name] = {}
            for method_name, details_data in methods_data.items():
                user_grouped_data[owner_name][method_name] = {
                    "filename": filename, "details": details_data}
    return render_template(
        "index.html",
        user_grouped_data=user_grouped_data,
        app_settings=app_settings
    )
