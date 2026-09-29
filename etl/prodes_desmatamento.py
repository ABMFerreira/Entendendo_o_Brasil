"""
ETL — Indicador 6: Área de Desmatamento por Estado

Fonte: Base dos Dados (BigQuery) — basedosdados.br_inpe_prodes.municipio_bioma
(PRODES/INPE), sem sigla_uf direto — join com o diretório de municípios da
própria Base dos Dados (br_bd_diretorios_brasil.municipio) para obter a UF.

⚠️ ACHADO IMPORTANTE (corrigido nesta versão): a coluna 'desmatado' da fonte
é ÁREA ACUMULADA até aquele ano, não o incremento anual — confirmado ao ver
valores crescentes ano a ano para o mesmo município nos dados de exemplo, e
confirmado de novo pela implausibilidade dos totais brutos por estado (ex:
Bahia apareceria com >260 mil km² desmatados EM UM SÓ ANO, quase metade do
território do estado — logicamente impossível). O indicador certo
("área desmatada no ano") é a DIFERENÇA entre o acumulado do ano atual e o
do ano anterior, por município+bioma — calculado aqui com LAG() no SQL.

⚠️ LIMITAÇÃO DE COBERTURA (não é bug): o PRODES monitora a Amazônia Legal
desde 1988, mas outros biomas entraram no monitoramento sistemático bem mais
tarde. Isso pode gerar "primeiro ano observado" com incremento artificialmente
alto (na verdade é o acumulado histórico todo aparecendo de uma vez) — por
isso descartamos o primeiro ano de cada série município+bioma (sem par
anterior para calcular diferença), e pedimos um ano a mais no início da
consulta (ano_inicio - 1) só como base de cálculo, não exibido no resultado.

Somamos o incremento de todos os biomas presentes em cada estado, por ano.

Requer:
    pip install google-cloud-bigquery db-dtypes pandas --user

Uso:
    python prodes_desmatamento.py --credenciais ..\\credenciais\\chave.json --project SEU_PROJECT_ID --ano-inicio 2015 --ano-fim 2023

Saída: data/desmatamento_uf.csv
Colunas: ano, sigla_uf, area_desmatada_incremento_km2
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from google.cloud import bigquery
from google.oauth2 import service_account

from common import salvar_csv

QUERY = """
WITH acumulado_com_lag AS (
  SELECT
    p.ano,
    p.id_municipio,
    p.bioma,
    m.sigla_uf,
    p.desmatado,
    LAG(p.desmatado) OVER (
      PARTITION BY p.id_municipio, p.bioma ORDER BY p.ano
    ) AS desmatado_ano_anterior,
    LAG(p.ano) OVER (
      PARTITION BY p.id_municipio, p.bioma ORDER BY p.ano
    ) AS ano_anterior
  FROM `basedosdados.br_inpe_prodes.municipio_bioma` p
  INNER JOIN `basedosdados.br_bd_diretorios_brasil.municipio` m
    ON p.id_municipio = m.id_municipio
  WHERE p.ano BETWEEN @ano_inicio_base AND @ano_fim
)
SELECT
  ano,
  sigla_uf,
  SUM(GREATEST(desmatado - desmatado_ano_anterior, 0)) AS area_desmatada_incremento_km2
FROM acumulado_com_lag
WHERE desmatado_ano_anterior IS NOT NULL   -- descarta o 1º ano de cada série (sem par anterior)
  AND ano_anterior = ano - 1               -- exige ano imediatamente anterior (sem buracos na série)
  AND ano >= @ano_inicio                   -- o ano_inicio-1 era só base de cálculo, não sai no resultado
GROUP BY ano, sigla_uf
ORDER BY ano, sigla_uf
"""


def buscar_desmatamento(credenciais_path: str, project_id: str, ano_inicio: int, ano_fim: int):
    credentials = service_account.Credentials.from_service_account_file(credenciais_path)
    client = bigquery.Client(project=project_id, credentials=credentials)

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("ano_inicio_base", "INT64", ano_inicio - 1),
            bigquery.ScalarQueryParameter("ano_inicio", "INT64", ano_inicio),
            bigquery.ScalarQueryParameter("ano_fim", "INT64", ano_fim),
        ]
    )
    return client.query(QUERY, job_config=job_config).to_dataframe()


def main():
    parser = argparse.ArgumentParser(description="ETL Área de Desmatamento por UF (PRODES via Base dos Dados)")
    parser.add_argument("--credenciais", required=True, help="Caminho para o JSON da conta de serviço")
    parser.add_argument("--project", required=True, help="ID do seu projeto Google Cloud (faturamento)")
    parser.add_argument("--ano-inicio", type=int, default=2015)
    parser.add_argument("--ano-fim", type=int, default=2023)
    args = parser.parse_args()

    df = buscar_desmatamento(args.credenciais, args.project, args.ano_inicio, args.ano_fim)
    if not df.empty:
        salvar_csv(df, "desmatamento_uf.csv")
        print(f"Estados presentes: {sorted(df['sigla_uf'].unique())}")
        print(df.head(10).to_string(index=False))
    else:
        print("[AVISO] Nenhum dado retornado.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
