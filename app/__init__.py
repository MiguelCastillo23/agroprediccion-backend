from flask import Flask
from flask_cors import CORS
from config import Config

def create_app():
    """Factory para crear la aplicación Flask"""
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Habilitar CORS para permitir requests desde frontend
    CORS(app, resources={
        r"/api/*": {
            "origins": Config.ALLOWED_ORIGINS if hasattr(Config, 'ALLOWED_ORIGINS') else "*",
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    })
    
    # Registrar rutas
    from app.routes import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')
    
    return app