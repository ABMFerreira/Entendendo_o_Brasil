"""
ETL — Indicador 7: Mortalidade Infantil por Estado (série OFICIAL CORRIGIDA)

Fonte: IBGE/SIDRA, tabela 7362 — "Esperança de vida ao nascer e Taxa de
mortalidade infantil, por sexo", da pesquisa "Projeção da População".

Por que esta tabela, e não o cálculo direto do SIM/SINASC:
  O cálculo direto a partir dos microdados do SIM/SINASC (ver
  sim_sinasc_saude.py) subestima a mortalidade infantil, porque o registro
  de óbitos infantis é incompleto e essa incompletude varia por estado
  (pior no Norte/Nordeste — ver ficha técnica, indicador 7, para os números
  oficiais de sub-registro). A tabela 7362 já usa a metodologia demográfica
  do IBGE (Projeções da População), que corrige esse viés.

Detalhe técnico da tabela: a "periodicidade" formal da tabela é fixa em
2018 (ano de publicação/edição da projeção), mas o ANO DE REFERÊNCIA de
cada estimativa é uma CLASSIFICAÇÃO dentro da tabela (id 1933), cobrindo
2000 a 2060. Por isso a consulta usa 'periodos/2018' fixo e filtra o ano
real via 'classificacao=1933[...]'.

Variável: 1940 (Taxa de mortalidade infantil, ‰)
Classificação 'Sexo' (id 2): usamos só a categoria 6794 ('Total').

Uso:
    python ibge_mortalidade_infantil.py --anos 2015-2023

Saída: data/mortalidade_infantil_uf_oficial.csv
Colunas: ano, cod_uf, uf, taxa_mortalidade_infantil_oficial
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
import requests

from common import salvar_csv

TABELA = "7362"
VARIAVEL = "1940"
PERIODO_EDICAO = "2018"  # periodicidade fixa da tabela (é a edição, não o ano do dado)
CATEGORIA_SEXO_TOTAL = "6794"
CLASSIFICACAO_ANO = "1933"

# mapa ano -> id de categoria, construído a partir do diagnóstico manual da tabela
# (ids não seguem um padrão previsível, então listamos explicitamente)
ANOS_PARA_CATEGORIA = {
    2000: "116338", 2001: "116336", 2002: "116335", 2003: "116334", 2004: "116332",
    2005: "116331", 2006: "116330", 2007: "116329", 2008: "116327", 2009: "119270",
    2010: "4336", 2011: "12037", 2012: "13242", 2013: "49029", 2014: "49030",
    2015: "49031", 2016: "49032", 2017: "49033", 2018: "49034", 2019: "49035",
    2020: "49036", 2021: "49037", 2022: "49038", 2023: "49039", 2024: "49040",
    2025: "49041", 2026: "49042", 2027: "49043", 2028: "49044", 2029: "49045",
    2030: "49046", 2031: "49047", 2032: "49048", 2033: "49049", 2034: "49050",
    2035: "49051", 2036: "49052", 2037: "49053", 2038: "49054", 2039: "49055",
    2040: "49056", 2041: "49057", 2042: "49058", 2043: "49059", 2044: "49060",
    2045: "49061", 2046: "49062", 2047: "49063", 2048: "49064", 2049: "49065",
    2050: "49066", 2051: "49067", 2052: "49068", 2053: "49069", 2054: "49070",
    2055: "49071", 2056: "49072", 2057: "49073", 2058: "49074", 2059: "49075",
    2060: "49076",
}

BASE_URL = f"https://servicodados.ibge.gov.br/api/v3/agregados/{TABELA}/periodos/{PERIODO_EDICAO}/variaveis/{VARIAVEL}"


def _anos_para_ids(ano_inicio: int, ano_fim: int) -> list[str]:
    faltando = [a for a in range(ano_inicio, ano_fim + 1) if a not in ANOS_PARA_CATEGORIA]
    if faltando:
        print(
            f"[AVISO] Anos sem id de categoria mapeado (fora do dicionário): {faltando}. "
            "O mapa cobre 2000-2060; confira se o intervalo pedido está correto.",
            file=sys.stderr,
        )
    return [ANOS_PARA_CATEGORIA[a] for a in range(ano_inicio, ano_fim + 1) if a in ANOS_PARA_CATEGORIA]


def buscar_mortalidade_infantil_oficial(ano_inicio: int, ano_fim: int) -> pd.DataFrame:
    categorias_ano = _anos_para_ids(ano_inicio, ano_fim)
    if not categorias_ano:
        return pd.DataFrame()

    params = {
        "localidades": "N3[all]",
        "classificacao": f"2[{CATEGORIA_SEXO_TOTAL}]|{CLASSIFICACAO_ANO}[{','.join(categorias_ano)}]",
    }

    resp = requests.get(BASE_URL, params=params, timeout=60)
    if resp.status_code != 200:
        print(f"[ERRO] HTTP {resp.status_code} ao consultar {resp.url}", file=sys.stderr)
        print(f"[ERRO] Corpo da resposta: {resp.text[:500]}", file=sys.stderr)
        resp.raise_for_status()

    dados = resp.json()
    registros = []
    for variavel_bloco in dados:
        for resultado in variavel_bloco.get("resultados", []):
            # cada 'resultado' aqui corresponde a uma combinação de classificações
            # (sexo=Total, ano=X); o valor real do ano fica na classificação, não
            # no campo 'serie' (que sempre terá só a chave '2018', a periodicidade)
            classificacoes = resultado.get("classificacoes", [])
            ano_categoria = None
            for classif in classificacoes:
                if classif.get("id") == CLASSIFICACAO_ANO:
                    # categoria é um dict {id: nome}; pegamos o nome (é o próprio ano)
                    categoria_dict = classif.get("categoria", {})
                    if categoria_dict:
                        ano_categoria = int(list(categoria_dict.values())[0])
                    break

            for serie in resultado.get("series", []):
                localidade = serie["localidade"]
                cod_uf = localidade["id"]
                nome_uf = localidade["nome"]
                for _periodo_edicao, valor in serie["serie"].items():
                    if valor in ("-", "...", "X", ".."):
                        continue
                    registros.append(
                        {
                            "ano": ano_categoria,
                            "cod_uf": cod_uf,
                            "uf": nome_uf,
                            "taxa_mortalidade_infantil_oficial": float(valor),
                        }
                    )

    df = pd.DataFrame(registros)
    if df.empty:
        print(
            "[AVISO] Nenhum registro retornado. Confira os parâmetros de classificação "
            "com diagnostico_ibge.py 7362.",
            file=sys.stderr,
        )
    return df


def main():
    parser = argparse.ArgumentParser(
        description="ETL Mortalidade Infantil por UF — série oficial corrigida (IBGE/SIDRA 7362)"
    )
    parser.add_argument("--anos", default="2015-2023", help="Intervalo, ex: 2015-2023")
    args = parser.parse_args()

    if "-" in args.anos:
        ano_inicio, ano_fim = (int(a) for a in args.anos.split("-"))
    else:
        anos = [int(a) for a in args.anos.split(",")]
        ano_inicio, ano_fim = min(anos), max(anos)

    df = buscar_mortalidade_infantil_oficial(ano_inicio, ano_fim)
    if not df.empty:
        df = df.sort_values(["ano", "uf"]).reset_index(drop=True)
        salvar_csv(df, "mortalidade_infantil_uf_oficial.csv")
        print(df.head(10).to_string(index=False))
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
