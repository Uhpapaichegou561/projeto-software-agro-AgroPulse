import os
from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
import database

app = Flask(__name__)

# 1. SECRET_KEY protegida (Usa variável de ambiente ou chave aleatória dinâmica de 24 bytes)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))

database.criar_tabela()
database.popular_dados_exemplo()


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
    """Sanitiza e valida rigorosamente as entradas do formulário."""
    nome = form.get("nome", "").strip()
    tipo = form.get("tipo", "").strip()

    # Validação de campos obrigatórios vazios
    if not nome or not tipo:
        raise ValueError("Os campos Nome e Tipo da máquina são obrigatórios.")

    try:
        horimetro_atual = float(form.get("horimetro_atual", 0))
        consumo_diesel = float(form.get("consumo_diesel_litros_hora", 0))
        custo_diesel = float(form.get("custo_diesel_litro", 0))
        ultima_manutencao = float(form.get("ultima_manutencao_horimetro", 0))
        intervalo_manutencao = float(form.get("intervalo_manutencao_horas", 0))
    except (ValueError, TypeError):
        raise ValueError("Todos os campos numéricos devem conter valores válidos.")

    # Proteção contra valores negativos
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


@app.route('/')
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
def relatorio():
    maquinas_calc = [calcular_indicadores(m) for m in database.listar_maquinas()]
    return render_template('relatorio.html', maquinas=maquinas_calc)


@app.route('/editar/<int:maquina_id>', methods=['GET', 'POST'])
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
def deletar(maquina_id):
    database.deletar_maquina(maquina_id)
    flash("Máquina removida com sucesso!", "success")
    return redirect(url_for('relatorio'))


# Rota de Registro de Usuário demonstrando HASH de Senha
@app.route('/registrar-usuario', methods=['POST'])
def registrar_usuario():
    usuario = request.form.get("usuario", "").strip()
    senha = request.form.get("senha", "").strip()

    if not usuario or not senha:
        flash("Informe usuário e senha válidos.", "danger")
        return redirect(url_for('index'))

    # Gera Hash seguro da senha (PBKDF2/SHA256)
    senha_hash = generate_password_hash(senha)
    try:
        database.criar_usuario(usuario, senha_hash)
        flash("Usuário registrado com sucesso!", "success")
    except Exception:
        flash("Erro: Nome de usuário já cadastrado.", "danger")

    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True)