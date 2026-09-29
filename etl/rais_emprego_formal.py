"""
ETL — Indicador 5 (parte 2/2): Emprego Formal por Estado

Fonte: Base dos Dados (BigQuery) — br_me_rais.microdados_vinculos (RAIS,
Ministério do Trabalho). Tabela de 250 GB — a consulta abaixo agrega direto
no SQL (COUNT + GROUP BY) para nunca trazer os microdados brutos ao cliente,
mantendo o custo de consulta baixo.

Métrica: vínculos formais ATIVOS EM 31/12 (campo 'vinculo_ativo_3112' = '1'),
que é o jeito padrão de medir "estoque de emprego formal" — confirmado por
inspeção: valores possíveis são '1' (ativo) e '0' (não ativo em 31/12).

Também calculamos vínculos formais por 1.000 habitantes, reaproveitando o
CSV de população já gerado pelo indicador 1 (mesmo padrão do indicador 9).
É necessário já ter rodado ibge_sidra_pib.py antes deste script.

Requer:
    pip install google-cloud-bigquery db-dtypes pandas --user

Uso:
    python rais_emprego_formal.py --credenciais ..\\credenciais\\chave.json --project SEU_PROJECT_ID --ano-inicio 2015 --ano-fim 2023

Saída: data/emprego_formal_uf.csv
Colunas: ano, sigla_uf, vinculos_ativos, populacao, vinculos_por_mil_habitantes
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account

from common import ESTADOS_SIGLA, DATA_DIR, salvar_csv

QUERY = """
SELECT
  ano,
  sigla_uf,
  COUNT(*) AS vinculos_ativos
FROM `basedosdados.br_me_rais.microdados_vinculos`
WHERE vinculo_ativo_3112 = '1'
  AND ano BETWEEN @ano_inicio AND @ano_fim
GROUP BY ano, sigla_uf
ORDER BY ano, sigla_uf
"""


def buscar_emprego_formal(credenciais_path: str, project_id: str, ano_inicio: int, ano_fim: int) -> pd.DataFrame:
    credentials = service_account.Credentials.from_service_account_file(credenciais_path)
    client = bigquery.Client(project=project_id, credentials=credentials)

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("ano_inicio", "INT64", ano_inicio),
            bigquery.ScalarQueryParameter("ano_fim", "INT64", ano_fim),
        ]
    )
    df = client.query(QUERY, job_config=job_config).to_dataframe()

    populacao_path = DATA_DIR / "pib_per_capita_uf.csv"
    if not populacao_path.exists():
        print(
            f"[AVISO] {populacao_path} não encontrado — rode ibge_sidra_pib.py primeiro. "
            "Retornando só os vínculos ativos, sem a taxa por 1.000 habitantes.",
            file=sys.stderr,
        )
        df["populacao"] = pd.NA
        df["vinculos_por_mil_habitantes"] = pd.NA
        return df

    df_pop = pd.read_csv(populacao_path)[["ano", "cod_uf", "populacao"]].drop_duplicates()
    df_pop["sigla_uf"] = df_pop["cod_uf"].astype(str).map(ESTADOS_SIGLA)

    df = df.merge(df_pop[["ano", "sigla_uf", "populacao"]], on=["ano", "sigla_uf"], how="left")
    df["vinculos_por_mil_habitantes"] = (df["vinculos_ativos"] / df["populacao"]) * 1000
    return df


def main():
    parser = argparse.ArgumentParser(description="ETL Emprego Formal por UF (RAIS via Base dos Dados)")
    parser.add_argument("--credenciais", required=True, help="Caminho para o JSON da conta de serviço")
    parser.add_argument("--project", required=True, help="ID do seu projeto Google Cloud (faturamento)")
    parser.add_argument("--ano-inicio", type=int, default=2015)
    parser.add_argument("--ano-fim", type=int, default=2023)
    args = parser.parse_args()

    df = buscar_emprego_formal(args.credenciais, args.project, args.ano_inicio, args.ano_fim)
    if not df.empty:
        salvar_csv(df, "emprego_formal_uf.csv")
        print(df.head(10).to_string(index=False))
    else:
        print("[AVISO] Nenhum dado retornado.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
