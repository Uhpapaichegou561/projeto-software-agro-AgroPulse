import os
import logging
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash
import database

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "agropulse-chave-secreta-ifro-2026")

# Configuração do arquivo dedicado de logs de auditoria
logging.basicConfig(
    filename="agropulse_auditoria.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Inicializa estrutura do banco e dados padrão no startup
database.criar_tabela()
database.popular_dados_exemplo()


# --- Decoradores de Segurança (Proteção de Rotas e RBAC) ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "usuario_id" not in session:
            flash("Acesso negado. Faça login para continuar.", "erro")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("nivel_acesso") != "admin":
            logging.warning(
                f"ACESSO_NEGADO_RBAC | Usuario: {session.get('username')} tentou executar rota restrita."
            )
            flash("Permissão negada: apenas administradores podem excluir registros.", "erro")
            return redirect(url_for("relatorio"))
        return f(*args, **kwargs)
    return decorated_function


# --- Regras de Negócio e Validação ---
def calcular_indicadores(maquina):
    """Calcula custo por hora e status de manutenção preventiva."""
    custo_hora = maquina["consumo_diesel_litros_hora"] * maquina["custo_diesel_litro"]
    horas_desde_manutencao = maquina["horimetro_atual"] - maquina["ultima_manutencao_horimetro"]
    horas_restantes = maquina["intervalo_manutencao_horas"] - horas_desde_manutencao
    alerta_manutencao = horas_restantes <= 0

    return {
        **maquina,
        "custo_hora": round(custo_hora, 2),
        "horas_desde_manutencao": round(horas_desde_manutencao, 1),
        "horas_restantes": round(horas_restantes, 1),
        "alerta_manutencao": alerta_manutencao,
    }


def ler_e_validar_formulario(form):
    """Valida tipos e regras numéricas no backend para evitar dados corrompidos."""
    nome = form.get("nome", "").strip()
    tipo = form.get("tipo", "").strip()
    if not nome or not tipo:
        raise ValueError("Nome e tipo da máquina são obrigatórios.")

    horimetro_atual = float(form.get("horimetro_atual", -1))
    consumo = float(form.get("consumo_diesel_litros_hora", -1))
    custo_diesel = float(form.get("custo_diesel_litro", -1))
    ultima_manutencao = float(form.get("ultima_manutencao_horimetro", -1))
    intervalo = float(form.get("intervalo_manutencao_horas", 0))

    if horimetro_atual < 0 or consumo < 0 or custo_diesel < 0 or ultima_manutencao < 0:
        raise ValueError("Valores numéricos não podem ser negativos.")
    if intervalo <= 0:
        raise ValueError("O intervalo de manutenção deve ser maior que zero.")
    if ultima_manutencao > horimetro_atual:
        raise ValueError("O horímetro da última manutenção não pode ser maior que o atual.")

    return {
        "nome": nome,
        "tipo": tipo,
        "horimetro_atual": horimetro_atual,
        "consumo_diesel_litros_hora": consumo,
        "custo_diesel_litro": custo_diesel,
        "ultima_manutencao_horimetro": ultima_manutencao,
        "intervalo_manutencao_horas": intervalo,
    }


# --- Rotas de Autenticação ---
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        senha = request.form.get("senha", "")
        usuario = database.buscar_usuario(username)

        if usuario and check_password_hash(usuario["senha_hash"], senha):
            session["usuario_id"] = usuario["id"]
            session["username"] = usuario["username"]
            session["nivel_acesso"] = usuario["nivel_acesso"]
            logging.info(f"LOGIN_SUCESSO | Usuario: {username} | Perfil: {usuario['nivel_acesso']}")
            flash(f"Bem-vindo ao AgroPulse, {username}!", "sucesso")
            return redirect(url_for("index"))

        logging.warning(f"LOGIN_FALHA | Tentativa invalida para usuario: {username}")
        flash("Usuário ou senha inválidos.", "erro")

    return render_template("login.html")


@app.route("/logout")
def logout():
    username = session.get("username", "desconhecido")
    logging.info(f"LOGOUT | Usuario: {username}")
    session.clear()
    flash("Sessão encerrada com segurança.", "sucesso")
    return redirect(url_for("login"))


# --- Rotas Protegidas do Sistema ---
@app.route("/")
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
        "index.html",
        total_maquinas=total_maquinas,
        alertas_ativos=alertas_ativos,
        custo_medio_hora=custo_medio_hora,
        maquinas=maquinas_calc,
    )


@app.route("/cadastrar", methods=["GET", "POST"])
@login_required
def cadastrar():
    if request.method == "POST":
        try:
            dados = ler_e_validar_formulario(request.form)
            database.inserir_maquina(dados)
            logging.info(f"CADASTRO_MAQUINA | Usuario: {session['username']} | Maquina: {dados['nome']}")
            flash("Máquina cadastrada com sucesso!", "sucesso")
            return redirect(url_for("relatorio"))
        except ValueError as erro:
            flash(f"Erro de validação: {erro}", "erro")

    return render_template("cadastro.html")


@app.route("/relatorio")
@login_required
def relatorio():
    maquinas_calc = [calcular_indicadores(m) for m in database.listar_maquinas()]
    return render_template("relatorio.html", maquinas=maquinas_calc)


@app.route("/editar/<int:maquina_id>", methods=["GET", "POST"])
@login_required
def editar(maquina_id):
    maquina = database.buscar_maquina(maquina_id)
    if maquina is None:
        flash("Máquina não encontrada.", "erro")
        return redirect(url_for("relatorio"))

    if request.method == "POST":
        try:
            dados = ler_e_validar_formulario(request.form)
            database.atualizar_maquina(maquina_id, dados)
            logging.info(f"EDICAO_MAQUINA | Usuario: {session['username']} | ID: {maquina_id}")
            flash("Registro atualizado com sucesso!", "sucesso")
            return redirect(url_for("relatorio"))
        except ValueError as erro:
            flash(f"Erro de validação: {erro}", "erro")

    return render_template("editar.html", maquina=maquina)


@app.route("/deletar/<int:maquina_id>", methods=["POST"])
@login_required
@admin_required
def deletar(maquina_id):
    maquina = database.buscar_maquina(maquina_id)
    if maquina:
        database.deletar_maquina(maquina_id)
        logging.info(
            f"EXCLUSAO_MAQUINA | Admin: {session['username']} | ID: {maquina_id} ({maquina['nome']})"
        )
        flash("Máquina excluída e registrada na auditoria.", "sucesso")
    return redirect(url_for("relatorio"))


# --- Tratamento Seguro de Erros ---
@app.errorhandler(404)
def pagina_nao_encontrada(e):
    return render_template("login.html"), 404


@app.errorhandler(500)
def erro_interno(e):
    logging.error(f"ERRO_INTERNO_500 | Detalhe: {e}")
    flash("Ocorreu um erro interno inesperado. Tente novamente.", "erro")
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=False)