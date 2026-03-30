from flask import Flask, request, jsonify, make_response
from database import CardDatabase
import functools

app = Flask(__name__)
db = CardDatabase()

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Session-ID",
    "Access-Control-Max-Age": "86400",
}


def apply_cors(response):
    for key, value in CORS_HEADERS.items():
        response.headers[key] = value
    return response


@app.after_request
def add_cors_headers(response):
    return apply_cors(response)


@app.route("/", defaults={"path": ""}, methods=["OPTIONS"])
@app.route("/<path:path>", methods=["OPTIONS"])
def handle_preflight(path):
    response = make_response("", 204)
    return apply_cors(response)


def require_auth(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        session_id = request.headers.get("X-Session-ID")
        if not session_id:
            return jsonify({"error": "Authentication required"}), 401

        user = db.get_session(session_id)
        if not user:
            return jsonify({"error": "Invalid or expired session"}), 401

        request.current_user = user
        return f(*args, **kwargs)
    return wrapper


def require_admin(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        session_id = request.headers.get("X-Session-ID")
        if not session_id:
            return jsonify({"error": "Authentication required"}), 401

        user = db.get_session(session_id)
        if not user:
            return jsonify({"error": "Invalid or expired session"}), 401

        if user.get("role") != "admin":
            return jsonify({"error": "Admin access required"}), 403

        request.current_user = user
        return f(*args, **kwargs)
    return wrapper


@app.route("/users", methods=["POST"])
def register_user():
    data = request.json
    if not data:
        return jsonify({"error": "Missing JSON body"}), 400

    required = ["first_name", "last_name", "email", "password"]
    for field in required:
        if not data.get(field, "").strip():
            return jsonify({"error": f"'{field}' is required"}), 400

    if len(data["password"]) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    user = db.create_user(data)
    if user is None:
        return jsonify({"error": "Email is already registered"}), 409

    return jsonify({
        "message": "User registered successfully",
        "user": user
    }), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.json
    if not data:
        return jsonify({"error": "Missing JSON body"}), 400

    email = data.get("email", "").strip()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    user = db.authenticate_user(email, password)
    if not user:
        return jsonify({"error": "Invalid email or password"}), 401

    session_id = db.create_session(user)

    return jsonify({
        "message": "Login successful",
        "session_id": session_id,
        "user": user
    }), 200


@app.route("/auth/logout", methods=["POST"])
def logout():
    session_id = request.headers.get("X-Session-ID")
    if session_id:
        db.delete_session(session_id)
    return jsonify({"message": "Logged out successfully"}), 200


# Public card browsing
@app.route("/cards", methods=["GET"])
def list_cards():
    return jsonify(db.get_all_cards())


@app.route("/cards/<int:card_id>", methods=["GET"])
def get_card(card_id):
    card = db.get_card(card_id)
    if card:
        return jsonify(card)
    return jsonify({"error": "Card not found"}), 404


# Admin-only inventory management
@app.route("/cards", methods=["POST"])
@require_admin
def create_card():
    data = request.json
    if not data:
        return jsonify({"error": "Missing JSON body"}), 400

    card = db.create_card(data)
    return jsonify(card), 201


@app.route("/cards/<int:card_id>", methods=["PUT"])
@require_admin
def update_card(card_id):
    data = request.json
    if not data:
        return jsonify({"error": "Missing JSON body"}), 400

    card = db.get_card(card_id)
    if not card:
        return jsonify({"error": "Card not found"}), 404

    updated_card = db.update_card(card_id, data)
    return jsonify(updated_card), 200


@app.route("/cards/<int:card_id>", methods=["DELETE"])
@require_admin
def delete_card(card_id):
    card = db.get_card(card_id)
    if not card:
        return jsonify({"error": "Card not found"}), 404

    db.delete_card(card_id)
    return jsonify({"message": "Card deleted successfully"}), 200


@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Invalid route"}), 404


@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({"error": "Method not allowed"}), 405


if __name__ == "__main__":
    app.run(debug=True)