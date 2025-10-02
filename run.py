from app import create_app
from config import Config

app = create_app()

if __name__ == '__main__':
    print("=" * 50)
    print("🚀 AGROPREDICCIÓN - API Backend")
    print("=" * 50)
    print(f"✅ Servidor corriendo en http://localhost:{Config.PORT}")
    print(f"📊 Ambiente: {Config.FLASK_ENV}")
    print("=" * 50)
    
    app.run(
        host='0.0.0.0',
        port=Config.PORT,
        debug=(Config.FLASK_ENV == 'development')
    )