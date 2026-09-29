"""
ETL — Indicador 4 (ampliado): Despesa por TODAS as funções de governo, por Estado

Fonte: Base dos Dados (BigQuery) — dataset `br_me_siconfi`, tabela
`uf_despesas_funcao`, que já processa os dados brutos do SICONFI (Tesouro
Nacional). Pivotamos para esta via depois que a API pública direta do
SICONFI se mostrou não confiável para automação (ver diagnostico_siconfi*.py
para o histórico dessa investigação).

Decisões de modelagem, confirmadas por inspeção real dos dados:
  - Usamos as linhas de TOTAL por função (id_conta_bd terminando em '.000'),
    não a soma manual das subfunções.
  - EXCLUÍMOS '3.00.000' ("Despesas Exceto Intraorçamentárias"), que é o
    total geral do estado, não uma função — incluí-la juntaria "a soma de
    tudo" como se fosse mais uma categoria, distorcendo qualquer análise de
    participação percentual por função.
  - Confirmamos que só existe o prefixo '3.' (nenhuma categoria econômica
    separada tipo despesas de capital em prefixo diferente), então o total
    por função já reflete o gasto completo, sem sub-representar investimento.
  - Fase da despesa: 'Despesas Liquidadas' por padrão — é a fase mais usada
    para medir execução orçamentária real (diferente de 'Empenhadas', que é
    só compromisso, e 'Pagas', que pode atrasar por restos a pagar).

Nota de qualidade de dados: a tabela tem uma pequena duplicidade em
'3.07.000' (aparece como "Relações Exteriores" e como "Demais Subfunções
Relações Exteriores"). Isso é tratado somando os valores dessas linhas na
consulta (GROUP BY id_conta_bd), então o script não quebra por causa disso —
mas vale reportar à Base dos Dados como possível inconsistência da fonte.

Requer:
    pip install google-cloud-bigquery db-dtypes --user

Autenticação: uma chave de conta de serviço (JSON) com papel "BigQuery User"
no SEU projeto Google Cloud (usado só para faturamento; o dataset em si é
público e gratuito, dentro da cota de 1 TB/mês).

Uso:
    python siconfi_despesas_funcao.py --credenciais ..\\credenciais\\chave.json --project SEU_PROJECT_ID --ano-inicio 2015 --ano-fim 2022

    # Para restringir a algumas funções específicas (opcional):
    python siconfi_despesas_funcao.py --credenciais ... --project ... --funcoes Saúde,Educação

Saída: data/despesas_funcao_uf.csv
Colunas: ano, uf, funcao, estagio, valor_reais
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from google.cloud import bigquery
from google.oauth2 import service_account

from common import salvar_csv

CODIGO_TOTAL_GERAL = "3.00.000"  # excluído: é o total do estado, não uma função

QUERY_TEMPLATE = """
SELECT
  ano,
  sigla_uf AS uf,
  conta_bd AS funcao,
  estagio_bd AS estagio,
  SUM(valor) AS valor_reais
FROM `basedosdados.br_me_siconfi.uf_despesas_funcao`
WHERE estagio_bd = @estagio
  AND id_conta_bd LIKE '3.%.000'
  AND id_conta_bd != @codigo_total_geral
  AND ano BETWEEN @ano_inicio AND @ano_fim
  {filtro_funcoes}
GROUP BY ano, uf, funcao, estagio
ORDER BY ano, uf, funcao
"""


def buscar_despesas_funcao(
    credenciais_path: str,
    project_id: str,
    ano_inicio: int,
    ano_fim: int,
    estagio: str,
    funcoes: list[str] | None,
):
    credentials = service_account.Credentials.from_service_account_file(credenciais_path)
    client = bigquery.Client(project=project_id, credentials=credentials)

    query_parameters = [
        bigquery.ScalarQueryParameter("estagio", "STRING", estagio),
        bigquery.ScalarQueryParameter("codigo_total_geral", "STRING", CODIGO_TOTAL_GERAL),
        bigquery.ScalarQueryParameter("ano_inicio", "INT64", ano_inicio),
        bigquery.ScalarQueryParameter("ano_fim", "INT64", ano_fim),
    ]

    filtro_funcoes = ""
    if funcoes:
        filtro_funcoes = "AND conta_bd IN UNNEST(@funcoes)"
        query_parameters.append(bigquery.ArrayQueryParameter("funcoes", "STRING", funcoes))

    query = QUERY_TEMPLATE.format(filtro_funcoes=filtro_funcoes)
    job_config = bigquery.QueryJobConfig(query_parameters=query_parameters)

    df = client.query(query, job_config=job_config).to_dataframe()
    return df


def main():
    parser = argparse.ArgumentParser(
        description="ETL Despesas por Função (todas, ou uma lista específica) por UF via Base dos Dados"
    )
    parser.add_argument("--credenciais", required=True, help="Caminho para o JSON da conta de serviço")
    parser.add_argument("--project", required=True, help="ID do seu projeto Google Cloud (faturamento)")
    parser.add_argument("--ano-inicio", type=int, default=2015)
    parser.add_argument("--ano-fim", type=int, default=2022)
    parser.add_argument(
        "--estagio",
        default="Despesas Liquidadas",
        help="Fase da despesa (padrão: Despesas Liquidadas)",
    )
    parser.add_argument(
        "--funcoes",
        default=None,
        help="Lista de funções separadas por vírgula (ex: 'Saúde,Educação'). Se omitido, traz TODAS.",
    )
    args = parser.parse_args()

    funcoes = [f.strip() for f in args.funcoes.split(",")] if args.funcoes else None

    df = buscar_despesas_funcao(
        args.credenciais, args.project, args.ano_inicio, args.ano_fim, args.estagio, funcoes
    )
    if not df.empty:
        salvar_csv(df, "despesas_funcao_uf.csv")
        print(f"Funções encontradas: {sorted(df['funcao'].unique())}")
        print(df.head(10).to_string(index=False))
    else:
        print("[AVISO] Nenhum dado retornado. Confira ano/estagio/funções.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

