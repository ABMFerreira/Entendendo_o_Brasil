"""
ETL — Indicadores 7 (Mortalidade Infantil) e 9 (Taxa de Homicídios) por Estado

Fontes: Base dos Dados (BigQuery)
  - br_ms_sim.microdados    (Sistema de Informações sobre Mortalidade, Ministério da Saúde)
  - br_ms_sinasc.microdados (Sistema de Nascidos Vivos, Ministério da Saúde)

Decisões de modelagem, confirmadas por inspeção real dos dados:

1. DEFINIÇÃO DE ÓBITO INFANTIL (< 1 ano):
   O campo 'idade' (já em anos) tem 0 para a maioria dos óbitos infantis, mas
   detectamos que ~34% dos óbitos claramente neonatais (nascimento e óbito na
   mesma data) vêm com 'idade' NULO em 2021 (2.670 de ~10.617 casos). Por
   isso, um óbito é considerado infantil se:
     idade = 0
     OU (idade é nulo E a diferença entre data_obito e data_nascimento < 365 dias)
   Usar só 'idade = 0' subestimaria a mortalidade infantil em cerca de 1/3.

2. Filtramos tipo_obito = 'nao-fetal' — excluímos natimortos (óbitos fetais),
   que não entram na definição padrão de mortalidade infantil (mortes de
   nascidos vivos).

3. TAXA DE HOMICÍDIOS: causa_basica no intervalo CID-10 'X85' a 'Y09'
   (capítulo "Agressões" da Classificação Internacional de Doenças).
   Comparação lexicográfica de string funciona aqui porque o formato é
   sempre 1 letra + 2 dígitos (X85...X99, depois Y00...Y09).

4. POPULAÇÃO: reaproveitamos o CSV já gerado pelo ETL do indicador 1
   (data/pib_per_capita_uf.csv), que já tem população por ano/UF vinda do
   IBGE. É necessário já ter rodado ibge_sidra_pib.py antes deste script.

Requer:
    pip install google-cloud-bigquery db-dtypes pandas --user

Uso:
    python sim_sinasc_saude.py --credenciais ..\\credenciais\\chave.json --project SEU_PROJECT_ID --ano-inicio 2015 --ano-fim 2023

Saídas:
    data/mortalidade_infantil_uf.csv  — ano, sigla_uf, obitos_infantis, nascidos_vivos, taxa_mortalidade_infantil
    data/taxa_homicidios_uf.csv       — ano, sigla_uf, obitos_homicidio, populacao, taxa_homicidios_100mil
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account

from common import ESTADOS_SIGLA, DATA_DIR, salvar_csv

QUERY_MORTALIDADE_INFANTIL = """
WITH obitos_infantis AS (
  SELECT ano, sigla_uf, COUNT(*) AS obitos_infantis
  FROM `basedosdados.br_ms_sim.microdados`
  WHERE tipo_obito = 'nao-fetal'
    AND ano BETWEEN @ano_inicio AND @ano_fim
    AND (
      idade = 0
      OR (
        idade IS NULL AND data_nascimento IS NOT NULL AND data_obito IS NOT NULL
        AND DATE_DIFF(data_obito, data_nascimento, DAY) < 365
      )
    )
  GROUP BY ano, sigla_uf
),
nascidos AS (
  SELECT ano, sigla_uf, COUNT(*) AS nascidos_vivos
  FROM `basedosdados.br_ms_sinasc.microdados`
  WHERE ano BETWEEN @ano_inicio AND @ano_fim
  GROUP BY ano, sigla_uf
)
SELECT
  n.ano,
  n.sigla_uf,
  COALESCE(oi.obitos_infantis, 0) AS obitos_infantis,
  n.nascidos_vivos,
  SAFE_DIVIDE(COALESCE(oi.obitos_infantis, 0), n.nascidos_vivos) * 1000 AS taxa_mortalidade_infantil
FROM nascidos n
LEFT JOIN obitos_infantis oi USING (ano, sigla_uf)
ORDER BY n.ano, n.sigla_uf
"""

QUERY_HOMICIDIOS = """
SELECT
  ano,
  sigla_uf,
  COUNT(*) AS obitos_homicidio
FROM `basedosdados.br_ms_sim.microdados`
WHERE tipo_obito = 'nao-fetal'
  AND ano BETWEEN @ano_inicio AND @ano_fim
  AND SUBSTR(causa_basica, 1, 3) BETWEEN 'X85' AND 'Y09'
GROUP BY ano, sigla_uf
ORDER BY ano, sigla_uf
"""


def _client(credenciais_path: str, project_id: str) -> bigquery.Client:
    credentials = service_account.Credentials.from_service_account_file(credenciais_path)
    return bigquery.Client(project=project_id, credentials=credentials)


def _job_config(ano_inicio: int, ano_fim: int) -> bigquery.QueryJobConfig:
    return bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("ano_inicio", "INT64", ano_inicio),
            bigquery.ScalarQueryParameter("ano_fim", "INT64", ano_fim),
        ]
    )


def buscar_mortalidade_infantil(client, ano_inicio, ano_fim) -> pd.DataFrame:
    job_config = _job_config(ano_inicio, ano_fim)
    return client.query(QUERY_MORTALIDADE_INFANTIL, job_config=job_config).to_dataframe()


def buscar_homicidios(client, ano_inicio, ano_fim) -> pd.DataFrame:
    job_config = _job_config(ano_inicio, ano_fim)
    df = client.query(QUERY_HOMICIDIOS, job_config=job_config).to_dataframe()

    populacao_path = DATA_DIR / "pib_per_capita_uf.csv"
    if not populacao_path.exists():
        print(
            f"[AVISO] {populacao_path} não encontrado — rode ibge_sidra_pib.py primeiro "
            "para gerar a população por UF. Retornando só os óbitos, sem taxa por 100 mil hab.",
            file=sys.stderr,
        )
        df["populacao"] = pd.NA
        df["taxa_homicidios_100mil"] = pd.NA
        return df

    df_pop = pd.read_csv(populacao_path)[["ano", "cod_uf", "populacao"]].drop_duplicates()
    df_pop["sigla_uf"] = df_pop["cod_uf"].astype(str).map(ESTADOS_SIGLA)

    df = df.merge(df_pop[["ano", "sigla_uf", "populacao"]], on=["ano", "sigla_uf"], how="left")
    df["taxa_homicidios_100mil"] = (df["obitos_homicidio"] / df["populacao"]) * 100000
    return df


def main():
    parser = argparse.ArgumentParser(
        description="ETL Mortalidade Infantil e Taxa de Homicídios por UF (SIM/SINASC via Base dos Dados)"
    )
    parser.add_argument("--credenciais", required=True, help="Caminho para o JSON da conta de serviço")
    parser.add_argument("--project", required=True, help="ID do seu projeto Google Cloud (faturamento)")
    parser.add_argument("--ano-inicio", type=int, default=2015)
    parser.add_argument("--ano-fim", type=int, default=2023)
    args = parser.parse_args()

    client = _client(args.credenciais, args.project)

    print("Buscando mortalidade infantil...")
    df_mi = buscar_mortalidade_infantil(client, args.ano_inicio, args.ano_fim)
    if not df_mi.empty:
        salvar_csv(df_mi, "mortalidade_infantil_uf.csv")
        print(df_mi.head(5).to_string(index=False))
    else:
        print("[AVISO] Nenhum dado de mortalidade infantil retornado.", file=sys.stderr)

    print("\nBuscando homicídios...")
    df_h = buscar_homicidios(client, args.ano_inicio, args.ano_fim)
    if not df_h.empty:
        salvar_csv(df_h, "taxa_homicidios_uf.csv")
        print(df_h.head(5).to_string(index=False))
    else:
        print("[AVISO] Nenhum dado de homicídios retornado.", file=sys.stderr)


if __name__ == "__main__":
    main()
