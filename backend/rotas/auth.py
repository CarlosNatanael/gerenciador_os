from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash
from database import get_db

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/')
def index():
    if 'usuario' in session:
        tipo_usuario = session.get('tipo')
        if tipo_usuario in ['admin', 'master-admin']:
            return redirect(url_for('admin.admin_dashboard'))
        elif tipo_usuario == 'manutencao':
            return redirect(url_for('manutencao.manutencao_dashboard'))
        elif tipo_usuario == 'solicitante':
            return redirect(url_for('solicitante.minhas_os')) 
        else:
            session.clear()
            flash('Tipo de usuário inválido na sessão.', 'warning')
            return redirect(url_for('auth.login'))
    return redirect(url_for('auth.login'))

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario_form = request.form.get('usuario', '').strip()
        senha_form = request.form.get('senha', '')

        if not usuario_form or not senha_form:
            flash('Usuário e senha são obrigatórios.', 'warning')
            return render_template('login.html')

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuarios WHERE usuario = ? AND ativo = 1", (usuario_form,))
        user_data = cursor.fetchone()

        if user_data:
            if check_password_hash(user_data['senha'], senha_form):
                session['usuario'] = user_data['usuario']
                session['tipo'] = user_data['tipo']
                session['user_id'] = user_data['id']

                if user_data['tipo'] == 'solicitante':
                    return redirect(url_for('solicitante.minhas_os'))
                elif user_data['tipo'] == 'manutencao':
                    return redirect(url_for('manutencao.manutencao_dashboard'))
                elif user_data['tipo'] in ['admin', 'master-admin']:
                    return redirect(url_for('admin.admin_dashboard'))
                else:
                    flash('Tipo de usuário desconhecido ou não autorizado.', 'danger')
                    session.clear()
                    return redirect(url_for('auth.login'))
            else:
                flash('Usuário ou senha inválidos, ou usuário inativo.', 'danger')
        else:
            flash('Usuário ou senha inválidos, ou usuário inativo.', 'danger')
            
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))