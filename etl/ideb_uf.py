"""
ETL — Indicador 8: IDEB por Estado (rede estadual)

Fonte: Base dos Dados (BigQuery) — basedosdados.br_inep_ideb.uf

A tabela vem quebrada por rede de ensino e etapa — não existe um "IDEB médio
do estado" único. Filtramos rede = 'estadual' (consistente com a definição
original da ficha técnica: "Estado, rede estadual") e trazemos as etapas
separadas (fundamental anos iniciais, anos finais, e médio), já que a
metodologia oficial do IDEB não combina essas etapas num número só.

Requer:
    pip install google-cloud-bigquery db-dtypes pandas --user

Uso:
    python ideb_uf.py --credenciais ..\\credenciais\\chave.json --project SEU_PROJECT_ID --ano-inicio 2015 --ano-fim 2023

Saída: data/ideb_uf.csv
Colunas: ano, sigla_uf, ensino, anos_escolares, ideb, taxa_aprovacao
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from google.cloud import bigquery
from google.oauth2 import service_account

from common import salvar_csv

QUERY = """
SELECT
  ano,
  sigla_uf,
  ensino,
  anos_escolares,
  ideb,
  taxa_aprovacao
FROM `basedosdados.br_inep_ideb.uf`
WHERE rede = 'estadual'
  AND ano BETWEEN @ano_inicio AND @ano_fim
  AND ideb IS NOT NULL
ORDER BY ano, sigla_uf, ensino, anos_escolares
"""


def buscar_ideb(credenciais_path: str, project_id: str, ano_inicio: int, ano_fim: int):
    credentials = service_account.Credentials.from_service_account_file(credenciais_path)
    client = bigquery.Client(project=project_id, credentials=credentials)

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("ano_inicio", "INT64", ano_inicio),
            bigquery.ScalarQueryParameter("ano_fim", "INT64", ano_fim),
        ]
    )
    return client.query(QUERY, job_config=job_config).to_dataframe()


def main():
    parser = argparse.ArgumentParser(description="ETL IDEB por UF, rede estadual (Base dos Dados)")
    parser.add_argument("--credenciais", required=True, help="Caminho para o JSON da conta de serviço")
    parser.add_argument("--project", required=True, help="ID do seu projeto Google Cloud (faturamento)")
    parser.add_argument("--ano-inicio", type=int, default=2015)
    parser.add_argument("--ano-fim", type=int, default=2023)
    args = parser.parse_args()

    df = buscar_ideb(args.credenciais, args.project, args.ano_inicio, args.ano_fim)
    if not df.empty:
        salvar_csv(df, "ideb_uf.csv")
        print(f"Combinações ensino/etapa encontradas: {df[['ensino', 'anos_escolares']].drop_duplicates().values.tolist()}")
        print(df.head(10).to_string(index=False))
    else:
        print("[AVISO] Nenhum dado retornado.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
