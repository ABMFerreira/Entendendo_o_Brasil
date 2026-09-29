"""
Consolidação dos 10 indicadores + upload para o Supabase (Postgres)

Lê todos os CSVs já gerados em ../data/ (pelos scripts de ETL), transforma
cada um num formato LONGO comum (ano, sigla_uf, id_indicador, dimensao,
valor) e sobe 3 tabelas para o Supabase:

  - dim_estado      : catálogo das 27 UFs
  - dim_indicador   : catálogo dos indicadores/sub-indicadores (com fonte,
                       unidade e descrição — puxado da ficha técnica)
  - fato_indicador  : todos os valores, num formato único e genérico

Por que formato longo: permite ao dashboard fazer UMA consulta genérica
("me dê o indicador X, estados Y/Z, anos A-B") em vez de ter lógica
diferente por indicador.

Alguns indicadores viram mais de um "id_indicador" porque a fonte já não
é um valor único por estado/ano (ex.: despesa por função tem uma função
por linha; IDEB tem uma etapa de ensino por linha). A coluna 'dimensao'
guarda esse detalhe quando existe, e fica vazia quando não existe.

Requer:
    pip install pandas sqlalchemy psycopg2-binary python-dotenv --user

Configuração: crie um arquivo ".env" (copie de ".env.example") com:
    SUPABASE_DB_URL=postgresql://postgres:SUA_SENHA@db.SEU_PROJETO.supabase.co:5432/postgres

Uso:
    python consolidar_supabase.py
    python consolidar_supabase.py --dry-run   # só mostra o que subiria, não escreve no banco
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
from dotenv import load_dotenv
import os

from common import ESTADOS, ESTADOS_SIGLA, REGIAO_POR_SIGLA, DATA_DIR

# Caminho explícito para o .env na raiz do projeto (um nível acima de etl/).
# Não depende de qual pasta você está quando roda o script.
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)
else:
    print(f"[AVISO] Arquivo .env não encontrado em {ENV_PATH}", file=sys.stderr)

# ---------------------------------------------------------------------------
# Catálogo de indicadores — id | nome | unidade | fonte | periodicidade
# ---------------------------------------------------------------------------
CATALOGO_INDICADORES = [
    {"id_indicador": "1_pib_per_capita", "nome": "PIB per capita", "unidade": "R$/habitante",
     "fonte": "IBGE/SIDRA (tabelas 5938 + 6579)", "periodicidade": "anual"},
    {"id_indicador": "2_gini", "nome": "Índice de Gini", "unidade": "índice (0-1)",
     "fonte": "IBGE/SIDRA (tabela 7435)", "periodicidade": "anual"},
    {"id_indicador": "3_idhm", "nome": "IDHM", "unidade": "índice (0-1)",
     "fonte": "Base dos Dados (mundo_onu_adh)", "periodicidade": "decenal (1991/2000/2010)"},
    {"id_indicador": "4_despesa_funcao", "nome": "Despesa por função", "unidade": "R$ (liquidado)",
     "fonte": "Base dos Dados (br_me_siconfi)", "periodicidade": "anual"},
    {"id_indicador": "5a_taxa_desocupacao", "nome": "Taxa de desocupação", "unidade": "%",
     "fonte": "IBGE/SIDRA (tabela 6396, média dos 4 trimestres)", "periodicidade": "anual"},
    {"id_indicador": "5b_emprego_formal", "nome": "Vínculos formais por mil habitantes", "unidade": "vínculos/1.000 hab.",
     "fonte": "Base dos Dados (br_me_rais)", "periodicidade": "anual"},
    {"id_indicador": "6_desmatamento", "nome": "Área desmatada (incremento anual)", "unidade": "km²",
     "fonte": "Base dos Dados (br_inpe_prodes)", "periodicidade": "anual"},
    {"id_indicador": "7_mortalidade_infantil", "nome": "Taxa de mortalidade infantil", "unidade": "óbitos/1.000 nascidos vivos",
     "fonte": "IBGE/SIDRA (tabela 7362, série oficial corrigida)", "periodicidade": "anual (usar só até 2023)"},
    {"id_indicador": "8_ideb", "nome": "IDEB (rede estadual)", "unidade": "índice (0-10)",
     "fonte": "Base dos Dados (br_inep_ideb)", "periodicidade": "bienal"},
    {"id_indicador": "9_taxa_homicidios", "nome": "Taxa de homicídios", "unidade": "óbitos/100.000 hab.",
     "fonte": "Base dos Dados (br_ms_sim)", "periodicidade": "anual"},
    {"id_indicador": "10a_saneamento_agua", "nome": "Atendimento de água", "unidade": "%",
     "fonte": "Base dos Dados (br_mdr_snis)", "periodicidade": "anual"},
    {"id_indicador": "10b_saneamento_esgoto", "nome": "Atendimento de esgoto", "unidade": "%",
     "fonte": "Base dos Dados (br_mdr_snis)", "periodicidade": "anual"},
]


def _sigla(df: pd.DataFrame) -> pd.Series:
    """Retorna a coluna sigla_uf, convertendo de cod_uf quando necessário."""
    if "sigla_uf" in df.columns:
        return df["sigla_uf"]
    if "cod_uf" in df.columns:
        return df["cod_uf"].astype(str).map(ESTADOS_SIGLA)
    raise ValueError("CSV sem sigla_uf nem cod_uf")


def _long(df: pd.DataFrame, id_indicador: str, coluna_valor: str, dimensao=None) -> pd.DataFrame:
    out = pd.DataFrame(
        {
            "ano": df["ano"],
            "sigla_uf": _sigla(df),
            "id_indicador": id_indicador,
            "dimensao": dimensao if dimensao is not None else "",
            "valor": df[coluna_valor],
        }
    )
    return out.dropna(subset=["valor"])


def montar_fato_indicador() -> pd.DataFrame:
    partes = []

    def ler(nome_arquivo):
        caminho = DATA_DIR / nome_arquivo
        if not caminho.exists():
            print(f"[AVISO] {caminho} não encontrado — pulando.", file=sys.stderr)
            return None
        return pd.read_csv(caminho)

    if (df := ler("pib_per_capita_uf.csv")) is not None:
        partes.append(_long(df, "1_pib_per_capita", "pib_per_capita_reais"))

    if (df := ler("gini_uf.csv")) is not None:
        partes.append(_long(df, "2_gini", "indice_gini"))

    if (df := ler("idhm_uf.csv")) is not None:
        partes.append(_long(df, "3_idhm", "idhm"))
        partes.append(_long(df, "3_idhm", "idhm_educacao", dimensao="educacao"))
        partes.append(_long(df, "3_idhm", "idhm_longevidade", dimensao="longevidade"))
        partes.append(_long(df, "3_idhm", "idhm_renda", dimensao="renda"))

    if (df := ler("despesas_funcao_uf.csv")) is not None:
        # uma linha por função — a própria coluna 'funcao' já é a dimensão
        # nota: este CSV usa a coluna 'uf' para guardar a SIGLA (não o nome
        # completo do estado, como nos outros arquivos) — renomeamos para
        # 'sigla_uf' para bater com o resto do pipeline.
        temp = df.rename(columns={"valor_reais": "valor", "uf": "sigla_uf"})
        for funcao, grupo in temp.groupby("funcao"):
            partes.append(_long(grupo, "4_despesa_funcao", "valor", dimensao=funcao))

    if (df := ler("taxa_desocupacao_uf.csv")) is not None:
        partes.append(_long(df, "5a_taxa_desocupacao", "taxa_desocupacao_media_anual"))

    if (df := ler("emprego_formal_uf.csv")) is not None:
        partes.append(_long(df, "5b_emprego_formal", "vinculos_por_mil_habitantes"))

    if (df := ler("desmatamento_uf.csv")) is not None:
        partes.append(_long(df, "6_desmatamento", "area_desmatada_incremento_km2"))

    if (df := ler("mortalidade_infantil_uf_oficial.csv")) is not None:
        partes.append(_long(df, "7_mortalidade_infantil", "taxa_mortalidade_infantil_oficial"))

    if (df := ler("ideb_uf.csv")) is not None:
        df["etapa"] = df["ensino"] + "_" + df["anos_escolares"]
        for etapa, grupo in df.groupby("etapa"):
            partes.append(_long(grupo, "8_ideb", "ideb", dimensao=etapa))

    if (df := ler("taxa_homicidios_uf.csv")) is not None:
        partes.append(_long(df, "9_taxa_homicidios", "taxa_homicidios_100mil"))

    if (df := ler("saneamento_uf.csv")) is not None:
        partes.append(_long(df, "10a_saneamento_agua", "taxa_atendimento_agua"))
        partes.append(_long(df, "10b_saneamento_esgoto", "taxa_atendimento_esgoto"))

    if not partes:
        raise RuntimeError("Nenhum CSV encontrado em data/ — rode os scripts de ETL primeiro.")

    fato = pd.concat(partes, ignore_index=True)
    fato["ano"] = fato["ano"].astype(int)
    return fato


def montar_dim_estado() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "cod_uf": cod,
                "sigla_uf": ESTADOS_SIGLA[cod],
                "nome_uf": nome,
                "regiao": REGIAO_POR_SIGLA[ESTADOS_SIGLA[cod]],
            }
            for cod, nome in ESTADOS.items()
        ]
    )


def montar_dim_indicador() -> pd.DataFrame:
    return pd.DataFrame(CATALOGO_INDICADORES)


def montar_dim_governador() -> pd.DataFrame | None:
    caminho = DATA_DIR / "governadores_uf.csv"
    if not caminho.exists():
        print(f"[AVISO] {caminho} não encontrado — rode governadores_uf.py primeiro. Pulando essa tabela.", file=sys.stderr)
        return None
    return pd.read_csv(caminho, parse_dates=["inicio_mandato", "fim_mandato"])


def subir_para_supabase(dim_estado, dim_indicador, fato_indicador, dim_governador=None):
    from sqlalchemy import create_engine

    db_url = os.getenv("SUPABASE_DB_URL")
    if not db_url or "SUA_SENHA" in db_url:
        print(
            f"[ERRO] SUPABASE_DB_URL não configurada corretamente (arquivo esperado: {ENV_PATH}).\n"
            "Confira:\n"
            "  1. O arquivo se chama exatamente '.env' (não '.env.txt' — no Windows, "
            "ative 'Mostrar extensões de arquivo' no Explorador para confirmar).\n"
            "  2. Está na RAIZ do projeto (mesma pasta do README.md), não dentro de etl/.\n"
            "  3. A linha dentro dele começa com 'SUPABASE_DB_URL=' (sem espaços antes do =).",
            file=sys.stderr,
        )
        sys.exit(1)

    engine = create_engine(db_url)
    dim_estado.to_sql("dim_estado", engine, if_exists="replace", index=False)
    dim_indicador.to_sql("dim_indicador", engine, if_exists="replace", index=False)
    fato_indicador.to_sql("fato_indicador", engine, if_exists="replace", index=False, chunksize=5000)
    tabelas = "dim_estado, dim_indicador, fato_indicador"
    if dim_governador is not None:
        dim_governador.to_sql("dim_governador", engine, if_exists="replace", index=False)
        tabelas += ", dim_governador"
    print(f"[OK] Tabelas escritas no Supabase: {tabelas}")


def main():
    parser = argparse.ArgumentParser(description="Consolida os CSVs de indicadores e sobe para o Supabase")
    parser.add_argument("--dry-run", action="store_true", help="Só mostra o resumo, não escreve no banco")
    args = parser.parse_args()

    dim_estado = montar_dim_estado()
    dim_indicador = montar_dim_indicador()
    fato_indicador = montar_fato_indicador()
    dim_governador = montar_dim_governador()

    print(f"dim_estado: {len(dim_estado)} linhas")
    print(f"dim_indicador: {len(dim_indicador)} linhas")
    print(f"fato_indicador: {len(fato_indicador)} linhas")
    if dim_governador is not None:
        print(f"dim_governador: {len(dim_governador)} linhas")
    print("\nContagem de linhas por indicador:")
    print(fato_indicador.groupby("id_indicador").size().to_string())

    if args.dry_run:
        print("\n[DRY RUN] Nada foi escrito no Supabase.")
        return

    subir_para_supabase(dim_estado, dim_indicador, fato_indicador, dim_governador)


if __name__ == "__main__":
    main()
