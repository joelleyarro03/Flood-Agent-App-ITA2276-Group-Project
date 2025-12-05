from flask import Flask
from flask_cors import CORS
from routes.geocode import bp as geocode_bp

def create_app():
    app = Flask(__name__)
    CORS(app)

    # Register blueprints
    from routes.health import bp as health_bp
    from routes.flood import bp as flood_bp
    from routes.hospital import bp as hospital_bp
    app.register_blueprint(health_bp, url_prefix="/api")
    app.register_blueprint(flood_bp, url_prefix="/api")
    app.register_blueprint(hospital_bp, url_prefix="/api")
    app.register_blueprint(geocode_bp, url_prefix="/api")

    @app.get("/")
    def root():
        return {"ok": True, "app": "Panacea backend"}

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(port=5001, debug=True)
