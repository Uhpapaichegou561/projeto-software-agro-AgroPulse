import sqlite3
from werkzeug.security import generate_password_hash

DB_NOME = "agrotrack.db"


def get_conexao():
    conexao = sqlite3.connect(DB_NOME)
    conexao.row_factory = sqlite3.Row
    conexao.execute("PRAGMA foreign_keys = ON;")
    return conexao


def criar_tabela():
    """Cria as tabelas relacionais e o gatilho de auditoria no SQLite."""
    conexao = get_conexao()

    # 1. Tabela principal de maquinário
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

    # 2. Tabela de usuários para autenticação e controle RBAC (Admin vs Operador)
    conexao.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            senha_hash TEXT NOT NULL,
            nivel_acesso TEXT NOT NULL CHECK(nivel_acesso IN ('admin', 'operador'))
        )
    """)

    # 3. Tabela de auditoria alimentada pelo Trigger do banco de dados
    conexao.execute("""
        CREATE TABLE IF NOT EXISTS auditoria_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            evento TEXT NOT NULL,
            maquina_id INTEGER,
            maquina_nome TEXT,
            data_hora DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 4. Trigger automático AFTER DELETE na tabela maquinas
    conexao.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_auditoria_delecao_maquina
        AFTER DELETE ON maquinas
        BEGIN
            INSERT INTO auditoria_log (evento, maquina_id, maquina_nome)
            VALUES ('EXCLUSAO_MAQUINA', OLD.id, OLD.nome);
        END;
    """)

    conexao.commit()
    conexao.close()


def popular_dados_exemplo():
    """Inicializa usuários padrão (com senha hash) e máquinas de exemplo."""
    conexao = get_conexao()

    # Cria usuários padrão caso não existam (Admin e Operador da Aplicação)
    total_usuarios = conexao.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]
    if total_usuarios == 0:
        usuarios_iniciais = [
            ("admin", generate_password_hash("Admin@Agro2026", method="pbkdf2:sha256"), "admin"),
            ("operador", generate_password_hash("Operador@2026", method="pbkdf2:sha256"), "operador"),
        ]
        conexao.executemany(
            "INSERT INTO usuarios (username, senha_hash, nivel_acesso) VALUES (?, ?, ?)",
            usuarios_iniciais,
        )

    # Cria máquinas de demonstração caso a tabela esteja vazia
    total_maquinas = conexao.execute("SELECT COUNT(*) FROM maquinas").fetchone()[0]
    if total_maquinas == 0:
        conexao.executemany("""
            INSERT INTO maquinas
            (nome, tipo, horimetro_atual, consumo_diesel_litros_hora,
             custo_diesel_litro, ultima_manutencao_horimetro, intervalo_manutencao_horas)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [
            ("Trator MF 4275", "Trator", 1180, 12.5, 6.10, 1000, 250),
            ("Colheitadeira Case 5088", "Colheitadeira", 940, 28.0, 6.10, 700, 200),
        ])

    conexao.commit()
    conexao.close()


def buscar_usuario(username):
    conexao = get_conexao()
    linha = conexao.execute(
        "SELECT * FROM usuarios WHERE username = ?", (username,)
    ).fetchone()
    conexao.close()
    return dict(linha) if linha else None


def listar_maquinas():
    conexao = get_conexao()
    linhas = conexao.execute("SELECT * FROM maquinas ORDER BY id").fetchall()
    conexao.close()
    return [dict(linha) for linha in linhas]


def buscar_maquina(maquina_id):
    conexao = get_conexao()
    linha = conexao.execute(
        "SELECT * FROM maquinas WHERE id = ?", (maquina_id,)
    ).fetchone()
    conexao.close()
    return dict(linha) if linha else None


def inserir_maquina(dados):
    conexao = get_conexao()
    conexao.execute("""
        INSERT INTO maquinas
        (nome, tipo, horimetro_atual, consumo_diesel_litros_hora,
         custo_diesel_litro, ultima_manutencao_horimetro, intervalo_manutencao_horas)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        dados["nome"], dados["tipo"], dados["horimetro_atual"],
        dados["consumo_diesel_litros_hora"], dados["custo_diesel_litro"],
        dados["ultima_manutencao_horimetro"], dados["intervalo_manutencao_horas"],
    ))
    conexao.commit()
    conexao.close()


def atualizar_maquina(maquina_id, dados):
    conexao = get_conexao()
    conexao.execute("""
        UPDATE maquinas SET
            nome = ?, tipo = ?, horimetro_atual = ?,
            consumo_diesel_litros_hora = ?, custo_diesel_litro = ?,
            ultima_manutencao_horimetro = ?, intervalo_manutencao_horas = ?
        WHERE id = ?
    """, (
        dados["nome"], dados["tipo"], dados["horimetro_atual"],
        dados["consumo_diesel_litros_hora"], dados["custo_diesel_litro"],
        dados["ultima_manutencao_horimetro"], dados["intervalo_manutencao_horas"],
        maquina_id,
    ))
    conexao.commit()
    conexao.close()


def deletar_maquina(maquina_id):
    conexao = get_conexao()
    conexao.execute("DELETE FROM maquinas WHERE id = ?", (maquina_id,))
    conexao.commit()
    conexao.close()