from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from datetime import datetime
from database import get_db

solicitante_bp = Blueprint('solicitante', __name__)

@solicitante_bp.route('/solicitante/abrir', methods=['GET', 'POST'])
def abrir_os():
    if session.get('tipo') not in ['solicitante', 'admin', 'master-admin']:
        flash('Acesso não autorizado para esta funcionalidade.', 'danger')
        return redirect(url_for('auth.login'))

    conn_get = get_db()
    cursor_get = conn_get.cursor()
    cursor_get.execute("SELECT id, nome FROM locais WHERE ativo = 1 ORDER BY nome")
    locais_ativos = cursor_get.fetchall()

    if request.method == 'POST':
        equipamento = request.form.get('equipamento', '').strip()
        problema = request.form.get('problema', '').strip()
        prioridade = request.form.get('prioridade')
        local_selecionado = request.form.get('local')
        setor = request.form.get('setor', '').strip()
        
        if not equipamento or not problema or not local_selecionado or not prioridade:
            flash('Preencha todos os campos obrigatórios.', 'danger')
            return render_template('solicitante/abrir_os.html', locais=locais_ativos, datetime=datetime, request_form_data=request.form)
        
        data_abertura = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        try:
            cursor_get.execute("SELECT id FROM usuarios WHERE usuario = ?", (session['usuario'],))
            user = cursor_get.fetchone()

            if not user:
                flash("Erro de sessão do usuário. Faça login novamente.", "danger")
                return redirect(url_for('auth.login'))

            cursor_get.execute("""
                INSERT INTO ordens_servico 
                (data, equipamento, problema, prioridade, status, solicitante_id, local, setor) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (data_abertura, equipamento, problema, prioridade, 'Aberta', user['id'], local_selecionado, setor))
            
            conn_get.commit()
            flash('Ordem de serviço enviada com sucesso! A equipe de manutenção fará o agendamento.', 'success')
            
            if session.get('tipo') == 'solicitante':
                return redirect(url_for('solicitante.minhas_os')) 
            else:
                return redirect(url_for('admin.admin_dashboard'))
            
        except Exception as e:
            conn_get.rollback()
            flash(f'Erro ao salvar OS: {str(e)}', 'danger')

        return render_template('solicitante/abrir_os.html', locais=locais_ativos, datetime=datetime, request_form_data=request.form)

    return render_template('solicitante/abrir_os.html', locais=locais_ativos, datetime=datetime)

@solicitante_bp.route('/solicitante/minhas_os')
def minhas_os():
    if session.get('tipo') != 'solicitante':
        return redirect(url_for('auth.login'))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM usuarios WHERE usuario = ?", (session['usuario'],))
    user = cursor.fetchone()
    
    cursor.execute("""
        SELECT os.*, u.nome as tecnico_nome
        FROM ordens_servico os
        LEFT JOIN usuarios u ON os.tecnico_id = u.id
        WHERE os.solicitante_id = ? AND os.status != 'Concluída'
        ORDER BY os.data DESC
    """, (user['id'],))
    os_abertas = cursor.fetchall()

    return render_template('solicitante/minhas_os.html', os_abertas=os_abertas)