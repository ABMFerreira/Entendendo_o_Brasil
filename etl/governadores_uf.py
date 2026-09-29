"""
Dimensão — Governadores Eleitos por Estado e Período de Mandato

Fonte: Base dos Dados (BigQuery) — basedosdados.br_tse_eleicoes.resultados_candidato,
filtrando cargo = 'governador' e resultado = 'eleito' (funciona tanto para
eleições resolvidas no 1º turno quanto no 2º turno — o mesmo candidato tem
uma linha com resultado='eleito' na apuração final, independente de quantos
turnos houve).

DERIVAÇÃO DO PERÍODO DE MANDATO: o TSE não publica data de posse/fim de
mandato nesta tabela — só o ano da eleição. Calculamos o período usando a
regra fixa da Constituição: mandato de governador é de 4 anos, começando em
1º de janeiro do ano seguinte à eleição.
    ano_eleicao=2018 → mandato 2019-01-01 a 2022-12-31

⚠️ LIMITAÇÃO CONHECIDA: essa regra NÃO captura mandatos interrompidos por
impeachment, renúncia, cassação ou falecimento (ex.: o vice assume e o
"governo" que executou o orçamento de fato pode ter sido outra pessoa por
parte do período). Para o MVP, aceitamos essa simplificação — sinalizar
claramente no site que a tabela reflete o CANDIDATO ELEITO, não
necessariamente quem exerceu o cargo o mandato inteiro. Refinar isso
(cruzando com atos de posse/afastamento) fica como melhoria futura.

⚠️ CASOS ESPECIAIS TRATADOS NESTA VERSÃO — 3 estados com mais de 1 "eleito"
no ciclo 2014, descobertos por auditoria dos dados (ver ficha técnica):

  - GOIÁS: Marconi Perillo aparece 2x (turno 1 e turno 2, mesmo candidato) —
    é a MESMA pessoa, duplicata trivial da fonte. Corrigido automaticamente
    aqui: mantemos só o turno mais alto.

  - AMAZONAS e TOCANTINS: são casos REAIS de dois governadores diferentes no
    mesmo ciclo 2014-2018 — o eleito original foi CASSADO pelo TSE (compra
    de votos / caixa 2) e substituído por outra pessoa, por vias e datas de
    transição que os relatos públicos não descrevem de forma totalmente
    consistente entre si. NÃO tentamos adivinhar a data exata da transição
    aqui — isso exigiria pesquisa histórica dedicada, fora do escopo de um
    script automatizado. Ambas as linhas são mantidas, marcadas com
    `requer_revisao_manual = True`, e o período de mandato (`inicio_mandato`/
    `fim_mandato`) fica em branco para essas linhas — preencher manualmente
    antes de usar esses 2 estados na análise de "impacto por gestão" do
    ciclo 2014-2018.

Requer:
    pip install google-cloud-bigquery db-dtypes pandas --user

Uso:
    python governadores_uf.py --credenciais ..\\credenciais\\chave.json --project SEU_PROJECT_ID --ano-inicio 2010 --ano-fim 2022

Saída: data/governadores_uf.csv
Colunas: ano_eleicao, sigla_uf, nome_candidato, sigla_partido, inicio_mandato, fim_mandato, requer_revisao_manual
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account

from common import salvar_csv

# Casos com 2 pessoas DIFERENTES no mesmo ciclo (cassação) — mantidos, mas
# sinalizados para revisão manual em vez de terem o período calculado.
CASOS_CASSACAO_CONHECIDOS = {(2014, "AM"), (2014, "TO")}

QUERY = """
SELECT
  ano AS ano_eleicao,
  sigla_uf,
  turno,
  nome_candidato,
  sigla_partido
FROM `basedosdados.br_tse_eleicoes.resultados_candidato`
WHERE cargo = 'governador'
  AND resultado = 'eleito'
  AND ano BETWEEN @ano_inicio AND @ano_fim
ORDER BY ano, sigla_uf, turno
"""


def buscar_governadores(credenciais_path: str, project_id: str, ano_inicio: int, ano_fim: int) -> pd.DataFrame:
    credentials = service_account.Credentials.from_service_account_file(credenciais_path)
    client = bigquery.Client(project=project_id, credentials=credentials)

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("ano_inicio", "INT64", ano_inicio),
            bigquery.ScalarQueryParameter("ano_fim", "INT64", ano_fim),
        ]
    )
    df = client.query(QUERY, job_config=job_config).to_dataframe()
    if df.empty:
        return df

    # --- Passo 1: resolver duplicatas do MESMO candidato em turnos diferentes
    # (caso Goiás) — mantém só o turno mais alto por (ano, uf, candidato).
    df = df.sort_values("turno").drop_duplicates(
        subset=["ano_eleicao", "sigla_uf", "nome_candidato", "sigla_partido"], keep="last"
    )

    # --- Passo 2: identificar linhas ainda duplicadas por (ano, uf) — agora
    # só sobram os casos de cassação com pessoas DIFERENTES.
    contagem = df.groupby(["ano_eleicao", "sigla_uf"])["nome_candidato"].transform("count")
    df["requer_revisao_manual"] = contagem > 1

    casos_nao_catalogados = set(
        df.loc[df["requer_revisao_manual"], ["ano_eleicao", "sigla_uf"]]
        .apply(tuple, axis=1)
        .unique()
    ) - CASOS_CASSACAO_CONHECIDOS
    if casos_nao_catalogados:
        print(
            f"[AVISO] Novos casos de duplicata não catalogados encontrados: {casos_nao_catalogados}. "
            "Investigar manualmente antes de confiar no período de mandato desses estados/anos.",
            file=sys.stderr,
        )

    df["inicio_mandato"] = pd.NaT
    df["fim_mandato"] = pd.NaT
    linhas_normais = ~df["requer_revisao_manual"]
    df.loc[linhas_normais, "inicio_mandato"] = pd.to_datetime(
        (df.loc[linhas_normais, "ano_eleicao"] + 1).astype(str) + "-01-01"
    )
    df.loc[linhas_normais, "fim_mandato"] = pd.to_datetime(
        (df.loc[linhas_normais, "ano_eleicao"] + 4).astype(str) + "-12-31"
    )

    return df.drop(columns="turno").sort_values(["ano_eleicao", "sigla_uf"])


def main():
    parser = argparse.ArgumentParser(description="Governadores eleitos por UF/período (TSE via Base dos Dados)")
    parser.add_argument("--credenciais", required=True, help="Caminho para o JSON da conta de serviço")
    parser.add_argument("--project", required=True, help="ID do seu projeto Google Cloud (faturamento)")
    parser.add_argument("--ano-inicio", type=int, default=2010, help="Ano de ELEIÇÃO inicial (não de mandato)")
    parser.add_argument("--ano-fim", type=int, default=2022, help="Ano de ELEIÇÃO final (não de mandato)")
    args = parser.parse_args()

    df = buscar_governadores(args.credenciais, args.project, args.ano_inicio, args.ano_fim)
    if not df.empty:
        salvar_csv(df, "governadores_uf.csv")
        print(f"Eleições cobertas: {sorted(df['ano_eleicao'].unique())}")
        print(df.head(10).to_string(index=False))
    else:
        print("[AVISO] Nenhum dado retornado.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
