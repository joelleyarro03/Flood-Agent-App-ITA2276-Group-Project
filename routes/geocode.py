from flask import Blueprint, request, jsonify
from services.nominatim import geocode

bp = Blueprint("geocode", __name__)

@bp.get("/geocode")
def geocode_route():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"results": []})
    try:
        results = geocode(q, limit=int(request.args.get("limit", 5)))
        return jsonify({"results": results})
    except Exception as e:
        # Fail soft with empty list (do not 500 during demos)
        print("[GEOCODE ERROR]", e)
        return jsonify({"results": []})
