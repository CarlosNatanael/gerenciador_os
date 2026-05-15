from flask import Blueprint, render_template, request, redirect, url_for, session, flash
import sqlite3
from functools import wraps
from datetime import datetime
from database import get_db

manutencao_bp = Blueprint('manutencao', __name__)

def manutencao_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('tipo') != 'manutencao':
            flash('Acesso não autorizado', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@manutencao_bp.route('/')
@manutencao_required
def manutencao_dashboard():
    if session.get('tipo') != 'manutencao':
        return redirect(url_for('auth.login'))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ordens_servico WHERE status != 'Concluída'")
    os_abertas = cursor.fetchall()

    return render_template('manutencao/listar_os.html', os_abertas=os_abertas)

@manutencao_bp.route('/concluir/<int:id_os>', methods=['POST'])
@manutencao_required
def concluir_os(id_os):
    if request.method == 'POST':
        solucao = request.form.get('solucao','').strip()
        data_conclusao_str = request.form.get('data_conclusao_manual')
        hora_conclusao_str = request.form.get('hora_conclusao_manual')
        ids_tecnicos_participantes = request.form.getlist('tecnicos_participantes')

        if not solucao or not data_conclusao_str or not hora_conclusao_str or not ids_tecnicos_participantes:
            flash('Solução, data/hora da conclusão e pelo menos um técnico participante são obrigatórios.', 'danger')
            conn_err = get_db()
            cursor_err = conn_err.cursor()
            cursor_err.execute("SELECT id, nome, tipo_tecnico as especialidade FROM tecnicos WHERE ativo = 1 ORDER BY nome")
            todos_tecnicos_err = cursor_err.fetchall()
            
            cursor_err.execute("SELECT * FROM ordens_servico WHERE id = ?", (id_os,))
            os_data_err = cursor_err.fetchone()

            return render_template('manutencao/detalhe_os.html', 
                                   os=dict(os_data_err) if os_data_err else None, 
                                   todos_tecnicos_manutencao=todos_tecnicos_err,
                                   request_form_data=request.form,
                                   datetime=datetime)

        try:
            fim_manual_dt_str = f"{data_conclusao_str} {hora_conclusao_str}:00"
            fim_manual_dt = datetime.strptime(fim_manual_dt_str, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            flash('Formato de data ou hora da conclusão inválido.', 'danger')
            conn_err = get_db()
            cursor_err = conn_err.cursor()
            cursor_err.execute("SELECT id, nome, tipo_tecnico as especialidade FROM tecnicos WHERE ativo = 1 ORDER BY nome")
            todos_tecnicos_err = cursor_err.fetchall()
            cursor_err.execute("SELECT * FROM ordens_servico WHERE id = ?", (id_os,))
            os_data_err = cursor_err.fetchone()
            return render_template('manutencao/detalhe_os.html', 
                                   os=dict(os_data_err) if os_data_err else None, 
                                   todos_tecnicos_manutencao=todos_tecnicos_err,
                                   request_form_data=request.form,
                                   datetime=datetime)

        conn = get_db()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT data, inicio FROM ordens_servico WHERE id = ?", (id_os,))
            os_data_db = cursor.fetchone()

            if not os_data_db:
                flash('OS não encontrada.', 'danger')
                return redirect(url_for('manutencao.manutencao_dashboard'))

            inicio_reparo_str = os_data_db['inicio'] if os_data_db['inicio'] else os_data_db['data']
            inicio_reparo_dt = datetime.strptime(inicio_reparo_str, '%Y-%m-%d %H:%M:%S')

            if fim_manual_dt < inicio_reparo_dt:
                flash('A data de conclusão não pode ser anterior à data de início/abertura da OS.', 'warning')
                cursor.execute("SELECT id, nome, tipo_tecnico as especialidade FROM tecnicos WHERE ativo = 1 ORDER BY nome")
                todos_tecnicos_err = cursor.fetchall()
                cursor.execute("SELECT * FROM ordens_servico WHERE id = ?", (id_os,))
                os_data_err = cursor.fetchone()
                return render_template('manutencao/detalhe_os.html', 
                                   os=dict(os_data_err) if os_data_err else None, 
                                   todos_tecnicos_manutencao=todos_tecnicos_err,
                                   request_form_data=request.form,
                                   datetime=datetime)


            tempo_total_segundos = (fim_manual_dt - inicio_reparo_dt).total_seconds()
            tempo_total_minutos = round(tempo_total_segundos / 60)
            inicio_final_para_db = inicio_reparo_str 
            
            cursor.execute("""
                UPDATE ordens_servico
                SET solucao = ?, 
                    status = 'Concluída', 
                    tempo_reparo = ?, 
                    fim = ?,
                    inicio = ?
                WHERE id = ?
            """, (solucao, tempo_total_minutos, fim_manual_dt.strftime('%Y-%m-%d %H:%M:%S'), inicio_final_para_db, id_os))
            
            cursor.execute("DELETE FROM participantes_os WHERE os_id = ?", (id_os,))
            
            for tecnico_id_str in ids_tecnicos_participantes:
                try:
                    tecnico_individual_id = int(tecnico_id_str)
                    cursor.execute("""
                        INSERT INTO participantes_os (os_id, tecnico_ref_id)
                        VALUES (?, ?)
                    """, (id_os, tecnico_individual_id))
                except ValueError:
                    flash(f"ID de técnico inválido encontrado: {tecnico_id_str}", "warning")
            
            cursor.execute("""
                INSERT INTO historico_os (os_id, usuario_id, acao, observacao)
                VALUES (?, ?, ?, ?)
            """, (id_os, session.get('user_id'), 'OS Concluída', f"Solução: {solucao}"))
            
            conn.commit()
            flash('OS concluída com sucesso!', 'success')
            return redirect(url_for('manutencao.detalhe_os', id_os=id_os))

        except sqlite3.Error as e:
            conn.rollback()
            flash(f'Erro de banco de dados ao concluir OS: {str(e)}', 'danger')
        except Exception as e:
            flash(f'Erro ao concluir OS: {str(e)}', 'danger')
        
        cursor.execute("SELECT id, nome, tipo_tecnico as especialidade FROM tecnicos WHERE ativo = 1 ORDER BY nome")
        todos_tecnicos_repop = cursor.fetchall()
        cursor.execute("SELECT * FROM ordens_servico WHERE id = ?", (id_os,))
        os_data_repop = cursor.fetchone()
        return render_template('manutencao/detalhe_os.html', 
                               os=dict(os_data_repop) if os_data_repop else None, 
                               todos_tecnicos_manutencao=todos_tecnicos_repop,
                               request_form_data=request.form,
                               datetime=datetime)

    return redirect(url_for('manutencao.manutencao_dashboard'))

@manutencao_bp.route('/iniciar/<int:id>')
@manutencao_required
def iniciar_os(id):
    if session.get('tipo') != 'manutencao':
        return redirect(url_for('auth.login'))

    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT status FROM ordens_servico WHERE id = ?", (id,))
        os_status = cursor.fetchone()['status']
        
        if os_status != 'Agendada':
            flash('Só é possível iniciar OSs agendadas', 'warning')
            return redirect(url_for('manutencao.manutencao_dashboard'))
        
        cursor.execute("""
            UPDATE ordens_servico 
            SET status = 'Em andamento',
                inicio = datetime('now')
            WHERE id = ?
        """, (id,))
        
        cursor.execute("""
            INSERT INTO historico_os 
            (os_id, usuario_id, acao)
            VALUES (?, ?, ?)
        """, (id, session.get('user_id'), 'Reparo iniciado'))
        
        conn.commit()
        flash('Reparo iniciado com sucesso!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Erro ao iniciar reparo: {str(e)}', 'danger')
    
    return redirect(url_for('manutencao.manutencao_dashboard'))

@manutencao_bp.route('/os/<int:id_os>')
@manutencao_required
def detalhe_os(id_os):
    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT os.*, 
                   s.nome as solicitante_nome,
                   s.email as solicitante_email,
                   u_tecnico_sistema.nome as nome_tecnico_sistema
            FROM ordens_servico os
            LEFT JOIN usuarios s ON os.solicitante_id = s.id
            LEFT JOIN usuarios u_tecnico_sistema ON os.tecnico_id = u_tecnico_sistema.id 
            WHERE os.id = ?
        """, (id_os,))
        os_data = cursor.fetchone()

        if not os_data:
            flash('Ordem de Serviço não encontrada.', 'danger')
            return redirect(url_for('manutencao.manutencao_dashboard'))

        os_dict = dict(os_data) 
        
        solicitante_info = {
            'nome': os_data['solicitante_nome'],
            'email': os_data['solicitante_email']
        } if os_data['solicitante_nome'] else None

        tecnico_sistema_info = {
            'nome': os_data['nome_tecnico_sistema']
        } if os_data['nome_tecnico_sistema'] else None

        cursor.execute("""
            SELECT h.*, u.nome as usuario_nome
            FROM historico_os h
            JOIN usuarios u ON h.usuario_id = u.id
            WHERE h.os_id = ?
            ORDER BY h.data_alteracao DESC
        """, (id_os,))
        historico = cursor.fetchall()

        todos_tecnicos_individuais = []
        if os_dict['status'] != 'Concluída' and os_dict['status'] != 'Cancelada':
            cursor.execute("""
                SELECT id, nome, tipo_tecnico 
                FROM tecnicos 
                WHERE ativo = 1 
                ORDER BY nome
            """)
            todos_tecnicos_individuais = [
                {'id': row['id'], 'nome': row['nome'], 'especialidade': row['tipo_tecnico']} 
                for row in cursor.fetchall()
            ]

        participantes_conclusao = []
        if os_dict['status'] == 'Concluída':
            cursor.execute("""
                SELECT t.id, t.nome, t.tipo_tecnico 
                FROM participantes_os po
                JOIN tecnicos t ON po.tecnico_ref_id = t.id
                WHERE po.os_id = ?
                ORDER BY t.nome
            """, (id_os,))
            participantes_conclusao = [
                {'id': row['id'], 'nome': row['nome'], 'especialidade': row['tipo_tecnico']}
                for row in cursor.fetchall()
            ]
        
        return render_template(
            'manutencao/detalhe_os.html',
            os=os_dict,
            solicitante=solicitante_info,
            tecnico=tecnico_sistema_info, 
            historico=historico,
            todos_tecnicos_manutencao=todos_tecnicos_individuais,
            participantes_conclusao=participantes_conclusao,
            datetime=datetime 
        )

    except Exception as e:
        print(f"Erro ao carregar detalhes da OS {id_os}: {str(e)}") 
        flash(f'Erro ao carregar detalhes da OS: {str(e)}', 'danger')
        return redirect(url_for('manutencao.manutencao_dashboard'))

@manutencao_bp.route('/agendar/<int:id_os>', methods=['GET', 'POST'])
@manutencao_required
def agendar_os(id_os):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM ordens_servico WHERE id = ?", (id_os,))
    os_data = cursor.fetchone()

    if not os_data:
        flash('Ordem de Serviço não encontrada.', 'danger')
        return redirect(url_for('manutencao.manutencao_dashboard'))

    if os_data['status'] in ['Concluída', 'Cancelada']:
        flash(f"OS #{id_os} já está {os_data['status'].lower()} e não pode ser reagendada.", 'warning')
        return redirect(url_for('manutencao.detalhe_os', id_os=id_os))

    if request.method == 'POST':
        data_agendamento_str = request.form.get('data_agendamento')
        horario_agendamento_str = request.form.get('horario_agendamento')
        
        if not data_agendamento_str or not horario_agendamento_str:
            flash('Data e horário são obrigatórios para o agendamento.', 'danger')
            return render_template('manutencao/agendar_os.html', 
                                   os=os_data, 
                                   request_form_data=request.form) 
        try:
            cursor.execute("""
                UPDATE ordens_servico 
                SET data_agendamento = ?, 
                    horario_agendamento = ?,
                    status = 'Agendada',
                    tecnico_id = ?  
                WHERE id = ?
            """, (data_agendamento_str, horario_agendamento_str, session.get('user_id'), id_os))
            
            observacao_historico = f"Agendado para {data_agendamento_str} {horario_agendamento_str}."

            cursor.execute("""
                INSERT INTO historico_os 
                (os_id, usuario_id, acao, observacao)
                VALUES (?, ?, ?, ?)
            """, (id_os, session.get('user_id'), 'OS Agendada', observacao_historico))
            
            conn.commit()
            flash('OS agendada com sucesso!', 'success')
            return redirect(url_for('manutencao.detalhe_os', id_os=id_os))

        except sqlite3.Error as e:
            conn.rollback()
            flash(f'Erro de banco de dados ao agendar OS: {str(e)}', 'danger')
        except Exception as e:
            flash(f'Erro ao agendar OS: {str(e)}', 'danger')
        
        return render_template('manutencao/agendar_os.html', 
                               os=os_data, 
                               request_form_data=request.form)

    return render_template('manutencao/agendar_os.html', 
                           os=os_data)

@manutencao_bp.route('/registros/novo', methods=['GET', 'POST'])
@manutencao_required
def novo_registro_direto():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, nome, tipo_tecnico 
        FROM tecnicos 
        WHERE ativo = 1 
        ORDER BY nome
    """)
    todos_tecnicos_manutencao = [
        {'id': row['id'], 'nome': row['nome'], 'especialidade': row['tipo_tecnico']}
        for row in cursor.fetchall()
    ]

    if request.method == 'POST':
        data_execucao_str = request.form.get('data_execucao')
        hora_execucao_str = request.form.get('hora_execucao')
        duracao_minutos_str = request.form.get('duracao_minutos')
        equipamento_afetado = request.form.get('equipamento_afetado','').strip()
        descricao_servico = request.form.get('descricao_servico','').strip()
        observacoes = request.form.get('observacoes','').strip()
        ids_tecnicos_participantes = request.form.getlist('tecnicos_participantes') 
        
        criado_por_id = session.get('user_id') 

        erros = []
        if not data_execucao_str: erros.append("Data da execução é obrigatória.")
        if not hora_execucao_str: erros.append("Hora da execução é obrigatória.")
        if not duracao_minutos_str: erros.append("Duração da operação é obrigatória.")
        if not descricao_servico: erros.append("Descrição do serviço é obrigatória.")
        if not ids_tecnicos_participantes: erros.append("Pelo menos um técnico participante deve ser selecionado.")

        data_execucao_completa_str = None
        if data_execucao_str and hora_execucao_str:
            try:
                data_execucao_completa_str = f"{data_execucao_str} {hora_execucao_str}:00"
                datetime.strptime(data_execucao_completa_str, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                erros.append("Formato de data ou hora da execução inválido.")
        
        duracao_minutos = None
        if duracao_minutos_str:
            try:
                duracao_minutos = int(duracao_minutos_str)
                if duracao_minutos <= 0:
                    erros.append("Duração da operação deve ser um número positivo.")
            except ValueError:
                erros.append("Duração da operação deve ser um número.")

        if erros:
            for erro in erros:
                flash(erro, 'danger')
            return render_template(
                'manutencao/novo_registro_direto.html',
                todos_tecnicos_manutencao=todos_tecnicos_manutencao, 
                datetime=datetime,
                request_form_data=request.form 
            )

        try:
            cursor.execute("""
                INSERT INTO registros_manutencao_direta 
                (data_execucao, duracao_minutos, equipamento_afetado, descricao_servico, observacoes, criado_por_id, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (data_execucao_completa_str, duracao_minutos, equipamento_afetado, descricao_servico, observacoes, criado_por_id, 'Pendente Aprovacao'))
            
            novo_registro_id = cursor.lastrowid

            for tecnico_id_str in ids_tecnicos_participantes:
                try:
                    tecnico_id = int(tecnico_id_str) 
                    cursor.execute("""
                        INSERT INTO participantes_registro_direto (registro_id, tecnico_ref_id)
                        VALUES (?, ?)
                    """, (novo_registro_id, tecnico_id))
                except ValueError:
                    print(f"Aviso: ID de técnico inválido '{tecnico_id_str}' ignorado para registro direto {novo_registro_id}")

            conn.commit()
            flash('Registro de manutenção direta criado com sucesso e pendente de aprovação!', 'success')
            return redirect(url_for('manutencao.manutencao_dashboard')) 

        except sqlite3.Error as e:
            conn.rollback()
            flash(f'Erro de banco de dados ao salvar o registro: {str(e)}', 'danger')
        except Exception as e:
            flash(f'Erro ao salvar o registro: {str(e)}', 'danger')
        
        return render_template(
            'manutencao/novo_registro_direto.html',
            todos_tecnicos_manutencao=todos_tecnicos_manutencao, 
            datetime=datetime,
            request_form_data=request.form 
        )

    return render_template(
        'manutencao/novo_registro_direto.html',
        todos_tecnicos_manutencao=todos_tecnicos_manutencao, 
        datetime=datetime
    )