from flask import Flask
from config import Config
from database import close_db

def create_app():
    app = Flask(__name__, 
                template_folder='../frontend/templates', 
                static_folder='../frontend/static')
    
    app.config.from_object(Config)
    app.teardown_appcontext(close_db)

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0')