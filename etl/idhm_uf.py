"""
ETL — Indicador 3: IDHM por Estado

Fonte: Base dos Dados (BigQuery) — `mundo_onu_adh.uf`, que já traz tratado
o Atlas do Desenvolvimento Humano (PNUD/Ipea/FJP).

⚠️ LIMITAÇÃO ESTRUTURAL DESTE INDICADOR (não é bug, é a natureza da fonte):
O IDHM é calculado a partir do Censo Demográfico, então só existe para os
anos de Censo: 1991, 2000 e 2010. Diferente dos outros indicadores do
projeto (anuais), este terá só 3 pontos no tempo por estado. Existe uma
versão mais recente baseada na PNAD Contínua (2022, 2024, ver Atlas Brasil
"Radar IDHM"), mas ela não está na Base dos Dados — exigiria raspar o site
atlasbrasil.org.br diretamente. Fora do escopo desta primeira versão.

Traz também os 3 subíndices (educação, longevidade, renda) — útil para a
plataforma mostrar qual dimensão puxa o IDHM de um estado para baixo.

Requer:
    pip install google-cloud-bigquery db-dtypes pandas --user

Uso:
    python idhm_uf.py --credenciais ..\\credenciais\\chave.json --project SEU_PROJECT_ID

Saída: data/idhm_uf.csv
Colunas: ano, sigla_uf, idhm, idhm_educacao, idhm_longevidade, idhm_renda
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
  idhm,
  idhm_e AS idhm_educacao,
  idhm_l AS idhm_longevidade,
  idhm_r AS idhm_renda
FROM `basedosdados.mundo_onu_adh.uf`
WHERE idhm IS NOT NULL
ORDER BY ano, sigla_uf
"""


def buscar_idhm(credenciais_path: str, project_id: str):
    credentials = service_account.Credentials.from_service_account_file(credenciais_path)
    client = bigquery.Client(project=project_id, credentials=credentials)
    return client.query(QUERY).to_dataframe()


def main():
    parser = argparse.ArgumentParser(description="ETL IDHM por UF (Base dos Dados)")
    parser.add_argument("--credenciais", required=True, help="Caminho para o JSON da conta de serviço")
    parser.add_argument("--project", required=True, help="ID do seu projeto Google Cloud (faturamento)")
    args = parser.parse_args()

    df = buscar_idhm(args.credenciais, args.project)
    if not df.empty:
        salvar_csv(df, "idhm_uf.csv")
        print(f"Anos disponíveis: {sorted(df['ano'].unique())}")
        print(df.head(10).to_string(index=False))
    else:
        print("[AVISO] Nenhum dado retornado.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
