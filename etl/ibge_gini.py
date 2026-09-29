"""
ETL — Indicador 2: Índice de Gini do Rendimento Domiciliar per Capita, por Estado

Fonte: IBGE/SIDRA, tabela 7435 (PNAD Contínua Anual), variável 10681.
Nível territorial N3 (Estado) confirmado via diagnostico_ibge.py 7435.
Sem classificações extras — a tabela já é direta (ano x localidade x valor).

Uso:
    python ibge_gini.py --anos 2015-2023

Saída: data/gini_uf.csv
Colunas: ano, cod_uf, uf, indice_gini
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
import requests

from common import salvar_csv

TABELA = "7435"
VARIAVEL = "10681"

BASE_URL = f"https://servicodados.ibge.gov.br/api/v3/agregados/{TABELA}/periodos/{{periodos}}/variaveis/{VARIAVEL}"


def buscar_gini(periodos: str) -> pd.DataFrame:
    url = BASE_URL.format(periodos=periodos)
    params = {"localidades": "N3[all]"}

    resp = requests.get(url, params=params, timeout=60)
    if resp.status_code != 200:
        print(f"[ERRO] HTTP {resp.status_code} ao consultar {resp.url}", file=sys.stderr)
        print(f"[ERRO] Corpo da resposta: {resp.text[:500]}", file=sys.stderr)
        resp.raise_for_status()

    dados = resp.json()
    registros = []
    for variavel_bloco in dados:
        for resultado in variavel_bloco.get("resultados", []):
            for serie in resultado.get("series", []):
                localidade = serie["localidade"]
                cod_uf = localidade["id"]
                nome_uf = localidade["nome"]
                for ano, valor in serie["serie"].items():
                    if valor in ("-", "...", "X", ".."):
                        continue
                    registros.append(
                        {
                            "ano": int(ano),
                            "cod_uf": cod_uf,
                            "uf": nome_uf,
                            "indice_gini": float(valor),
                        }
                    )

    df = pd.DataFrame(registros)
    if df.empty:
        print("[AVISO] Nenhum registro retornado.", file=sys.stderr)
    return df


def main():
    parser = argparse.ArgumentParser(description="ETL Índice de Gini por UF (IBGE/SIDRA)")
    parser.add_argument("--anos", default="2015-2023", help="Intervalo, ex: 2015-2023")
    args = parser.parse_args()

    df = buscar_gini(args.anos)
    if not df.empty:
        df = df.sort_values(["ano", "uf"]).reset_index(drop=True)
        salvar_csv(df, "gini_uf.csv")
        print(df.head(10).to_string(index=False))
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
