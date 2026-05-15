from flask import Flask
from config import Config
from database import close_db
from flask_wtf.csrf import CSRFProtect

# Importação dos Blueprints
from rotas.auth import auth_bp
from rotas.admin import admin_bp
from rotas.manutencao import manutencao_bp
from rotas.solicitante import solicitante_bp

def create_app():

    app = Flask(__name__, 
                template_folder='../frontend/templates', 
                static_folder='../frontend/static')
    
    app.config.from_object(Config)
    app.teardown_appcontext(close_db)

    csrf = CSRFProtect()
    csrf.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(manutencao_bp, url_prefix='/manutencao')
    app.register_blueprint(solicitante_bp, url_prefix='/solicitante')

    return app

# Instância da aplicação
app = create_app()

if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=False)