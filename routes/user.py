from flask import Blueprint, jsonify
from core.utils.profile import generate_user_profile

user_bp = Blueprint('user', __name__)

@user_bp.route("/user_profile/<username>")
def get_user_profile(username):
    profile_data = generate_user_profile(username)
    if profile_data:
        return jsonify(profile_data)
    else:
        return jsonify({"error": "User not found"}), 404