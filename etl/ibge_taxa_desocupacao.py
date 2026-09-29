"""
ETL — Indicador 5 (parte 1/2): Taxa de Desocupação por Estado

Fonte: IBGE/SIDRA, tabela 6396 (PNAD Contínua Trimestral), variável 4099.
Nível territorial N3 (Estado) confirmado via diagnostico_ibge.py 6396.

Metodologia: a tabela é trimestral (formato de período AAAAQQ, ex: '201501'
= 1º trimestre de 2015). Calculamos a MÉDIA DOS 4 TRIMESTRES de cada ano
como "taxa de desocupação anual" — evita escolher arbitrariamente um
trimestre (ex.: só o 4º) como representativo do ano inteiro.

Classificação 'Sexo' (id 2): usamos só a categoria 6794 ('Total').

Uso:
    python ibge_taxa_desocupacao.py --anos 2015-2023

Saída: data/taxa_desocupacao_uf.csv
Colunas: ano, cod_uf, uf, taxa_desocupacao_media_anual, trimestres_disponiveis
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
import requests

from common import salvar_csv

TABELA = "6396"
VARIAVEL = "4099"
CATEGORIA_SEXO_TOTAL = "6794"

BASE_URL = f"https://servicodados.ibge.gov.br/api/v3/agregados/{TABELA}/periodos/{{periodos}}/variaveis/{VARIAVEL}"


def buscar_taxa_desocupacao(ano_inicio: int, ano_fim: int) -> pd.DataFrame:
    periodos = f"{ano_inicio}01-{ano_fim}04"  # todos os trimestres do intervalo
    url = BASE_URL.format(periodos=periodos)
    params = {"localidades": "N3[all]", "classificacao": f"2[{CATEGORIA_SEXO_TOTAL}]"}

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
                for periodo, valor in serie["serie"].items():
                    if valor in ("-", "...", "X", ".."):
                        continue
                    ano = int(periodo[:4])
                    trimestre = int(periodo[4:6])
                    registros.append(
                        {
                            "ano": ano,
                            "trimestre": trimestre,
                            "cod_uf": cod_uf,
                            "uf": nome_uf,
                            "taxa_desocupacao": float(valor),
                        }
                    )

    df_trimestral = pd.DataFrame(registros)
    if df_trimestral.empty:
        print("[AVISO] Nenhum registro retornado.", file=sys.stderr)
        return df_trimestral

    df_anual = (
        df_trimestral.groupby(["ano", "cod_uf", "uf"])
        .agg(
            taxa_desocupacao_media_anual=("taxa_desocupacao", "mean"),
            trimestres_disponiveis=("taxa_desocupacao", "count"),
        )
        .reset_index()
    )
    return df_anual.sort_values(["ano", "uf"]).reset_index(drop=True)


def main():
    parser = argparse.ArgumentParser(description="ETL Taxa de Desocupação por UF (IBGE/SIDRA)")
    parser.add_argument("--anos", default="2015-2023", help="Intervalo, ex: 2015-2023")
    args = parser.parse_args()
    ano_inicio, ano_fim = (int(a) for a in args.anos.split("-"))

    df = buscar_taxa_desocupacao(ano_inicio, ano_fim)
    if not df.empty:
        salvar_csv(df, "taxa_desocupacao_uf.csv")
        print(df.head(10).to_string(index=False))
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
