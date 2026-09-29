"""
Módulo compartilhado de acesso a dados do dashboard.

Importado tanto por app.py (página inicial) quanto pelas páginas em pages/.
Centraliza a conexão com o Supabase e as consultas, todas com cache.
"""
import os
from pathlib import Path

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine


@st.cache_resource
def get_engine():
    db_url = None
    try:
        if "SUPABASE_DB_URL" in st.secrets:
            db_url = st.secrets["SUPABASE_DB_URL"]
    except Exception:
        pass  # sem secrets.toml configurado (normal em execução local)

    if not db_url:
        from dotenv import load_dotenv

        env_path = Path(__file__).resolve().parent.parent / ".env"
        load_dotenv(env_path)
        db_url = os.getenv("SUPABASE_DB_URL")

    if not db_url:
        st.error(
            "SUPABASE_DB_URL não configurada. Localmente, crie um .env na raiz "
            "do projeto (copie de .env.example). No Streamlit Cloud, configure "
            "em Settings → Secrets."
        )
        st.stop()

    return create_engine(db_url)


@st.cache_data(ttl=3600)
def carregar_dim_estado() -> pd.DataFrame:
    return pd.read_sql("SELECT * FROM dim_estado ORDER BY nome_uf", get_engine())


@st.cache_data(ttl=3600)
def carregar_dim_indicador() -> pd.DataFrame:
    return pd.read_sql("SELECT * FROM dim_indicador ORDER BY id_indicador", get_engine())


@st.cache_data(ttl=3600)
def carregar_dados_indicador(id_indicador: str) -> pd.DataFrame:
    """Traz TODAS as linhas de um indicador (todos os estados, todas as
    dimensões) — os filtros são aplicados depois, em memória, para não
    precisar de uma ida ao banco por combinação de filtro."""
    query = "SELECT ano, sigla_uf, dimensao, valor FROM fato_indicador WHERE id_indicador = %(id_indicador)s"
    return pd.read_sql(query, get_engine(), params={"id_indicador": id_indicador})


@st.cache_data(ttl=3600)
def carregar_dim_governador() -> pd.DataFrame:
    df = pd.read_sql("SELECT * FROM dim_governador", get_engine())
    df["inicio_mandato"] = pd.to_datetime(df["inicio_mandato"])
    df["fim_mandato"] = pd.to_datetime(df["fim_mandato"])
    return df


def mandatos_do_estado(sigla_uf: str) -> pd.DataFrame:
    """Mandatos de um estado, ordenados, prontos para desenhar no gráfico."""
    df = carregar_dim_governador()
    return df[(df["sigla_uf"] == sigla_uf) & (~df["requer_revisao_manual"])].sort_values("inicio_mandato")


def expandir_com_agregados(dados: pd.DataFrame, dim_estado: pd.DataFrame) -> pd.DataFrame:
    """
    Recebe um DataFrame (ano, sigla_uf, dimensao, valor) e devolve um novo
    DataFrame com uma coluna 'entidade' que inclui, além dos estados
    individuais (pelo nome), também a média de cada região e a média do
    Brasil — para permitir comparar "meu estado" com agregados maiores.

    Usado na página de Análise Cruzada (comparar gasto x indicador).
    """
    base = dados.merge(dim_estado[["sigla_uf", "nome_uf", "regiao"]], on="sigla_uf", how="left")

    estados_df = base[["ano", "dimensao", "valor", "nome_uf"]].rename(columns={"nome_uf": "entidade"})

    regioes_df = (
        base.groupby(["ano", "dimensao", "regiao"])["valor"].mean().reset_index().rename(columns={"regiao": "entidade"})
    )
    regioes_df["entidade"] = "Região " + regioes_df["entidade"]

    brasil_df = base.groupby(["ano", "dimensao"])["valor"].mean().reset_index()
    brasil_df["entidade"] = "Brasil (média)"

    return pd.concat([estados_df, regioes_df, brasil_df], ignore_index=True)
