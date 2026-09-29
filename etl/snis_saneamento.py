"""
ETL — Indicador 10: % de Atendimento de Água e Esgoto por Estado

Fonte: Base dos Dados (BigQuery) — basedosdados.br_mdr_snis.municipio_agua_esgoto
(SNIS/Ministério do Desenvolvimento Regional), nível município, com sigla_uf
já disponível direto na tabela (sem necessidade de join).

⚠️ ACHADO IMPORTANTE (corrigido nesta versão): a primeira tentativa calculou
a taxa dividindo 'populacao_atendida_agua' por 'populacao_urbana' somadas por
estado, e deu estados com MAIS de 100% de atendimento (ex: Bahia 108%,
Alagoas 102%) — logicamente impossível. As duas colunas de população vêm de
fontes/definições ligeiramente diferentes dentro do SNIS e não são
perfeitamente comparáveis ao somar por município.

Correção: usamos os ÍNDICES JÁ CALCULADOS OFICIALMENTE pelo próprio SNIS por
município ('indice_atendimento_total_agua' e 'indice_coleta_esgoto'), e
agregamos por estado com MÉDIA PONDERADA PELA POPULAÇÃO (peso =
populacao_urbana) — mais confiável do que recalcular a divisão nós mesmos.

⚠️ Nota residual: mesmo os índices oficiais do SNIS podem eventualmente
passar de 100% em algum município (é dado autodeclarado pelos prestadores de
serviço, sem auditoria external padronizada — limitação conhecida do SNIS).
Se isso acontecer no agregado por estado, documentar no site como
característica da fonte, não tentar "corrigir" arbitrariamente o valor.

Requer:
    pip install google-cloud-bigquery db-dtypes pandas --user

Uso:
    python snis_saneamento.py --credenciais ..\\credenciais\\chave.json --project SEU_PROJECT_ID --ano-inicio 2015 --ano-fim 2023

Saída: data/saneamento_uf.csv
Colunas: ano, sigla_uf, taxa_atendimento_agua, taxa_atendimento_esgoto
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
  SAFE_DIVIDE(
    SUM(indice_atendimento_total_agua * populacao_urbana),
    SUM(populacao_urbana)
  ) AS taxa_atendimento_agua,
  SAFE_DIVIDE(
    SUM(indice_coleta_esgoto * populacao_urbana),
    SUM(populacao_urbana)
  ) AS taxa_atendimento_esgoto
FROM `basedosdados.br_mdr_snis.municipio_agua_esgoto`
WHERE ano BETWEEN @ano_inicio AND @ano_fim
  AND populacao_urbana IS NOT NULL
  AND populacao_urbana > 0
GROUP BY ano, sigla_uf
ORDER BY ano, sigla_uf
"""


def buscar_saneamento(credenciais_path: str, project_id: str, ano_inicio: int, ano_fim: int):
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
    parser = argparse.ArgumentParser(description="ETL Atendimento Água/Esgoto por UF (SNIS via Base dos Dados)")
    parser.add_argument("--credenciais", required=True, help="Caminho para o JSON da conta de serviço")
    parser.add_argument("--project", required=True, help="ID do seu projeto Google Cloud (faturamento)")
    parser.add_argument("--ano-inicio", type=int, default=2015)
    parser.add_argument("--ano-fim", type=int, default=2023)
    args = parser.parse_args()

    df = buscar_saneamento(args.credenciais, args.project, args.ano_inicio, args.ano_fim)
    if not df.empty:
        salvar_csv(df, "saneamento_uf.csv")
        print(df.head(10).to_string(index=False))
    else:
        print("[AVISO] Nenhum dado retornado.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
