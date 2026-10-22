import os
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
import database

app = Flask(__name__)

# 1. Configuração da SECRET_KEY protegida (necessária para sessões e flash messages)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))

database.criar_tabela()
database.popular_dados_exemplo()

# Decorador de Proteção de Rotas (Exige Login)
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario_id' not in session:
            flash("Por favor, faça login para acessar esta página.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def calcular_indicadores(maquina):
    """Calcula custo por hora e status de manutenção de uma máquina."""
    custo_hora = maquina["consumo_diesel_litros_hora"] * maquina["custo_diesel_litro"]
    horas_desde_manutencao = maquina["horimetro_atual"] - maquina["ultima_manutencao_horimetro"]
    horas_restantes = maquina["intervalo_manutencao_horas"] - horas_desde_manutencao
    alerta_manutencao = horas_restantes <= 0

    return {
        **maquina,
        "custo_hora": round(custo_hora, 2),
        "horas_desde_manutencao": horas_desde_manutencao,
        "horas_restantes": horas_restantes,
        "alerta_manutencao": alerta_manutencao,
    }


def ler_e_validar_formulario(form):
    """Sanitiza e valida rigorosamente as entradas do formulário de máquina."""
    nome = form.get("nome", "").strip()
    tipo = form.get("tipo", "").strip()

    if not nome or not tipo:
        raise ValueError("Os campos Nome e Tipo da máquina são obrigatórios.")

    try:
        horimetro_atual = float(form.get("horimetro_atual", 0))
        consumo_diesel = float(form.get("consumo_diesel_litros_hora", 0))
        custo_diesel = float(form.get("custo_diesel_litro", 0))
        ultima_manutencao = float(form.get("ultima_manutencao_horimetro", 0))
        intervalo_manutencao = float(form.get("intervalo_manutencao_horas", 0))
    except (ValueError, TypeError):
        raise ValueError("Todos os campos numéricos devem conter valores numéricos válidos.")

    if any(val < 0 for val in [horimetro_atual, consumo_diesel, custo_diesel, ultima_manutencao, intervalo_manutencao]):
        raise ValueError("Valores numéricos não podem ser negativos.")

    return {
        "nome": nome,
        "tipo": tipo,
        "horimetro_atual": horimetro_atual,
        "consumo_diesel_litros_hora": consumo_diesel,
        "custo_diesel_litro": custo_diesel,
        "ultima_manutencao_horimetro": ultima_manutencao,
        "intervalo_manutencao_horas": intervalo_manutencao,
    }


# --- ROTAS DE AUTENTICAÇÃO (LOGIN / REGISTRO / LOGOUT) ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario_input = request.form.get("usuario", "").strip()
        senha_input = request.form.get("senha", "").strip()

        if not usuario_input or not senha_input:
            flash("Preencha todos os campos.", "danger")
            return render_template('login.html')

        user = database.buscar_usuario_por_nome(usuario_input)

        # Valida usuário e checa a senha contra o Hash gravado
        if user and check_password_hash(user['senha_hash'], senha_input):
            session['usuario_id'] = user['id']
            session['usuario_nome'] = user['usuario']
            flash(f"Bem-vindo(a), {user['usuario']}!", "success")
            return redirect(url_for('index'))
        else:
            flash("Usuário ou senha incorretos.", "danger")

    return render_template('login.html')


@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        usuario_input = request.form.get("usuario", "").strip()
        senha_input = request.form.get("senha", "").strip()

        if not usuario_input or not senha_input:
            flash("Preencha o nome de usuário e a senha.", "danger")
            return render_template('registro.html')

        if len(senha_input) < 6:
            flash("A senha deve conter no mínimo 6 caracteres.", "warning")
            return render_template('registro.html')

        # Criação segura com Hash (PBKDF2/SHA256)
        senha_hash = generate_password_hash(senha_input)

        try:
            database.criar_usuario(usuario_input, senha_hash)
            flash("Conta criada com sucesso! Faça login para continuar.", "success")
            return redirect(url_for('login'))
        except Exception:
            flash("Nome de usuário já está em uso.", "danger")

    return render_template('registro.html')


@app.route('/logout')
def logout():
    session.clear()
    flash("Sua sessão foi encerrada.", "info")
    return redirect(url_for('login'))


# --- ROTAS PROTEGIDAS DO SISTEMA ---

@app.route('/')
@login_required
def index():
    maquinas_calc = [calcular_indicadores(m) for m in database.listar_maquinas()]
    total_maquinas = len(maquinas_calc)
    alertas_ativos = sum(1 for m in maquinas_calc if m["alerta_manutencao"])
    custo_medio_hora = (
        round(sum(m["custo_hora"] for m in maquinas_calc) / total_maquinas, 2)
        if total_maquinas > 0 else 0
    )

    return render_template(
        'index.html',
        total_maquinas=total_maquinas,
        alertas_ativos=alertas_ativos,
        custo_medio_hora=custo_medio_hora,
        maquinas=maquinas_calc,
    )


@app.route('/cadastrar', methods=['GET', 'POST'])
@login_required
def cadastrar():
    if request.method == 'POST':
        try:
            dados = ler_e_validar_formulario(request.form)
            database.inserir_maquina(dados)
            flash("Máquina cadastrada com sucesso!", "success")
            return redirect(url_for('relatorio'))
        except ValueError as e:
            flash(f"Erro de Validação: {str(e)}", "danger")

    return render_template('cadastro.html')


@app.route('/relatorio')
@login_required
def relatorio():
    maquinas_calc = [calcular_indicadores(m) for m in database.listar_maquinas()]
    return render_template('relatorio.html', maquinas=maquinas_calc)


@app.route('/editar/<int:maquina_id>', methods=['GET', 'POST'])
@login_required
def editar(maquina_id):
    maquina = database.buscar_maquina(maquina_id)
    if maquina is None:
        flash("Máquina não encontrada.", "warning")
        return redirect(url_for('relatorio'))

    if request.method == 'POST':
        try:
            dados = ler_e_validar_formulario(request.form)
            database.atualizar_maquina(maquina_id, dados)
            flash("Registro atualizado com sucesso!", "success")
            return redirect(url_for('relatorio'))
        except ValueError as e:
            flash(f"Erro ao atualizar: {str(e)}", "danger")

    return render_template('editar.html', maquina=maquina)


@app.route('/deletar/<int:maquina_id>', methods=['POST'])
@login_required
def deletar(maquina_id):
    database.deletar_maquina(maquina_id)
    flash("Máquina removida com sucesso!", "success")
    return redirect(url_for('relatorio'))


if __name__ == '__main__':
    app.run(debug=True)