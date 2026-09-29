"""
ETL — Indicador 1: PIB per capita por Estado (IBGE/SIDRA)

O IBGE não publica "PIB per capita por UF" como variável pronta em nenhuma
tabela do SIDRA (confirmado via diagnóstico em diagnostico_ibge.py). Por isso,
calculamos aqui a partir de duas tabelas oficiais:

  - Tabela 5938 (pesquisa "Produto Interno Bruto dos Municípios"): PIB total
    a preços correntes, variável 37, em Mil Reais. Suporta nível N3 (UF).
  - Tabela 6579 (pesquisa "Estimativas de População"): população residente
    estimada, variável 9324, em Pessoas. Suporta nível N3 (UF).

PIB per capita = (PIB em Mil Reais * 1000) / População

Uso:
    python ibge_sidra_pib.py --anos 2015-2022
    python ibge_sidra_pib.py --anos 2019,2020,2021

Saída: data/pib_per_capita_uf.csv
Colunas: ano, cod_uf, uf, pib_mil_reais, populacao, pib_per_capita_reais
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
import requests

from common import salvar_csv

TABELA_PIB = "5938"
VARIAVEL_PIB = "37"
TABELA_POP = "6579"
VARIAVEL_POP = "9324"

BASE_URL = "https://servicodados.ibge.gov.br/api/v3/agregados/{tabela}/periodos/{periodos}/variaveis/{variavel}"


def _buscar_serie(tabela: str, variavel: str, periodos: str, nome_valor: str) -> pd.DataFrame:
    """Busca uma variável do SIDRA para todos os estados (N3) e retorna formato longo."""
    url = BASE_URL.format(tabela=tabela, periodos=periodos, variavel=variavel)
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
                            nome_valor: float(valor),
                        }
                    )
    return pd.DataFrame(registros)


def buscar_pib_per_capita(periodos: str) -> pd.DataFrame:
    df_pib = _buscar_serie(TABELA_PIB, VARIAVEL_PIB, periodos, "pib_mil_reais")
    df_pop = _buscar_serie(TABELA_POP, VARIAVEL_POP, periodos, "populacao")

    if df_pib.empty or df_pop.empty:
        print("[AVISO] Uma das duas séries (PIB ou população) veio vazia.", file=sys.stderr)
        return pd.DataFrame()

    df = df_pib.merge(df_pop, on=["ano", "cod_uf", "uf"], how="inner")
    df["pib_per_capita_reais"] = (df["pib_mil_reais"] * 1000) / df["populacao"]
    df = df.sort_values(["ano", "uf"]).reset_index(drop=True)
    return df


def main():
    parser = argparse.ArgumentParser(description="ETL PIB per capita por UF (IBGE/SIDRA, calculado)")
    parser.add_argument(
        "--anos",
        default="2015-2022",
        help="Intervalo (ex: 2015-2022) ou lista separada por vírgula (ex: 2019,2020,2021)",
    )
    args = parser.parse_args()

    df = buscar_pib_per_capita(args.anos)
    if not df.empty:
        salvar_csv(df, "pib_per_capita_uf.csv")
        print(df.head(10).to_string(index=False))
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
