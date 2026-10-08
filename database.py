import sqlite3

DB_NOME = "agroPulse.db"

def get_conexao():
    conexao = sqlite3.connect(DB_NOME)
    conexao.row_factory = sqlite3.Row
    return conexao

def criar_tabela():
    conexao = get_conexao()
    # Tabela de Máquinas
    conexao.execute("""
        CREATE TABLE IF NOT EXISTS maquinas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            tipo TEXT NOT NULL,
            horimetro_atual REAL NOT NULL,
            consumo_diesel_litros_hora REAL NOT NULL,
            custo_diesel_litro REAL NOT NULL,
            ultima_manutencao_horimetro REAL NOT NULL,
            intervalo_manutencao_horas REAL NOT NULL
        )
    """)
    # Tabela de Usuários para autenticação segura com Hash
    conexao.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT UNIQUE NOT NULL,
            senha_hash TEXT NOT NULL
        )
    """)
    conexao.commit()
    conexao.close()

def popular_dados_exemplo():
    conexao = get_conexao()
    cursor = conexao.cursor()
    cursor.execute("SELECT COUNT(*) FROM maquinas")
    if cursor.fetchone()[0] == 0:
        conexao.execute("""
            INSERT INTO maquinas (nome, tipo, horimetro_atual, consumo_diesel_litros_hora, custo_diesel_litro, ultima_manutencao_horimetro, intervalo_manutencao_horas)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ("Trator Massey Ferguson 4292", "Trator", 1250.0, 12.5, 5.80, 1000.0, 250.0))
        conexao.commit()
    conexao.close()

def listar_maquinas():
    conexao = get_conexao()
    maquinas = conexao.execute("SELECT * FROM maquinas").fetchall()
    conexao.close()
    return [dict(m) for m in maquinas]

def buscar_maquina(maquina_id):
    conexao = get_conexao()
    maquina = conexao.execute("SELECT * FROM maquinas WHERE id = ?", (maquina_id,)).fetchone()
    conexao.close()
    return dict(maquina) if maquina else None

def inserir_maquina(dados):
    conexao = get_conexao()
    conexao.execute("""
        INSERT INTO maquinas (nome, tipo, horimetro_atual, consumo_diesel_litros_hora, custo_diesel_litro, ultima_manutencao_horimetro, intervalo_manutencao_horas)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        dados["nome"], dados["tipo"], dados["horimetro_atual"],
        dados["consumo_diesel_litros_hora"], dados["custo_diesel_litro"],
        dados["ultima_manutencao_horimetro"], dados["intervalo_manutencao_horas"]
    ))
    conexao.commit()
    conexao.close()

def atualizar_maquina(maquina_id, dados):
    conexao = get_conexao()
    conexao.execute("""
        UPDATE maquinas
        SET nome = ?, tipo = ?, horimetro_atual = ?, consumo_diesel_litros_hora = ?,
            custo_diesel_litro = ?, ultima_manutencao_horimetro = ?, intervalo_manutencao_horas = ?
        WHERE id = ?
    """, (
        dados["nome"], dados["tipo"], dados["horimetro_atual"],
        dados["consumo_diesel_litros_hora"], dados["custo_diesel_litro"],
        dados["ultima_manutencao_horimetro"], dados["intervalo_manutencao_horas"], maquina_id
    ))
    conexao.commit()
    conexao.close()

def deletar_maquina(maquina_id):
    conexao = get_conexao()
    conexao.execute("DELETE FROM maquinas WHERE id = ?", (maquina_id,))
    conexao.commit()
    conexao.close()

# Funções de Usuário com Segurança contra SQL Injection
def criar_usuario(usuario, senha_hash):
    conexao = get_conexao()
    conexao.execute("INSERT INTO usuarios (usuario, senha_hash) VALUES (?, ?)", (usuario, senha_hash))
    conexao.commit()
    conexao.close()

def buscar_usuario(usuario):
    conexao = get_conexao()
    user = conexao.execute("SELECT * FROM usuarios WHERE usuario = ?", (usuario,)).fetchone()
    conexao.close()
    return dict(user) if user else None