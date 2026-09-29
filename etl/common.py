"""
Utilitários compartilhados pelos scripts de ETL do projeto.
"""
from pathlib import Path

# Códigos IBGE de 2 dígitos das 26 UFs + DF
ESTADOS = {
    "11": "Rondônia", "12": "Acre", "13": "Amazonas", "14": "Roraima",
    "15": "Pará", "16": "Amapá", "17": "Tocantins", "21": "Maranhão",
    "22": "Piauí", "23": "Ceará", "24": "Rio Grande do Norte", "25": "Paraíba",
    "26": "Pernambuco", "27": "Alagoas", "28": "Sergipe", "29": "Bahia",
    "31": "Minas Gerais", "32": "Espírito Santo", "33": "Rio de Janeiro",
    "35": "São Paulo", "41": "Paraná", "42": "Santa Catarina",
    "43": "Rio Grande do Sul", "50": "Mato Grosso do Sul", "51": "Mato Grosso",
    "52": "Goiás", "53": "Distrito Federal",
}

# Sigla <-> código, útil para cruzar com outras fontes (ex: PRODES usa sigla)
ESTADOS_SIGLA = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP",
    "17": "TO", "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB",
    "26": "PE", "27": "AL", "28": "SE", "29": "BA", "31": "MG", "32": "ES",
    "33": "RJ", "35": "SP", "41": "PR", "42": "SC", "43": "RS", "50": "MS",
    "51": "MT", "52": "GO", "53": "DF",
}

# Região por sigla — usado para calcular médias regionais no dashboard
REGIAO_POR_SIGLA = {
    "AC": "Norte", "AP": "Norte", "AM": "Norte", "PA": "Norte", "RO": "Norte",
    "RR": "Norte", "TO": "Norte",
    "AL": "Nordeste", "BA": "Nordeste", "CE": "Nordeste", "MA": "Nordeste",
    "PB": "Nordeste", "PE": "Nordeste", "PI": "Nordeste", "RN": "Nordeste",
    "SE": "Nordeste",
    "DF": "Centro-Oeste", "GO": "Centro-Oeste", "MS": "Centro-Oeste", "MT": "Centro-Oeste",
    "ES": "Sudeste", "MG": "Sudeste", "RJ": "Sudeste", "SP": "Sudeste",
    "PR": "Sul", "RS": "Sul", "SC": "Sul",
}

# Região oficial (IBGE) de cada UF, por sigla — usado para calcular médias
# regionais no dashboard.
REGIAO_POR_SIGLA = {
    "AC": "Norte", "AP": "Norte", "AM": "Norte", "PA": "Norte", "RO": "Norte",
    "RR": "Norte", "TO": "Norte",
    "AL": "Nordeste", "BA": "Nordeste", "CE": "Nordeste", "MA": "Nordeste",
    "PB": "Nordeste", "PE": "Nordeste", "PI": "Nordeste", "RN": "Nordeste",
    "SE": "Nordeste",
    "DF": "Centro-Oeste", "GO": "Centro-Oeste", "MS": "Centro-Oeste", "MT": "Centro-Oeste",
    "ES": "Sudeste", "MG": "Sudeste", "RJ": "Sudeste", "SP": "Sudeste",
    "PR": "Sul", "RS": "Sul", "SC": "Sul",
}

# Diretório onde cada script salva seu CSV de saída
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)


def salvar_csv(df, nome_arquivo: str):
    """Salva um DataFrame em /data com nome padronizado e imprime um resumo."""
    caminho = DATA_DIR / nome_arquivo
    df.to_csv(caminho, index=False, encoding="utf-8")
    print(f"[OK] {len(df)} linhas salvas em {caminho}")
    return caminho


def buscar_populacao_ibge(periodos: str):
    """
    Busca população residente estimada por UF (IBGE/SIDRA, tabela 6579,
    variável 9324), a mesma fonte já validada no ETL de PIB per capita.
    Retorna DataFrame com colunas: ano, cod_uf, sigla_uf, populacao.

    Reutilizável por qualquer indicador que precise de população como
    denominador (ex.: taxas por 100 mil habitantes).
    """
    import pandas as pd
    import requests

    url = (
        "https://servicodados.ibge.gov.br/api/v3/agregados/6579"
        f"/periodos/{periodos}/variaveis/9324"
    )
    resp = requests.get(url, params={"localidades": "N3[all]"}, timeout=60)
    resp.raise_for_status()
    dados = resp.json()

    registros = []
    for variavel in dados:
        for resultado in variavel.get("resultados", []):
            for serie in resultado.get("series", []):
                cod_uf = serie["localidade"]["id"]
                for ano, valor in serie["serie"].items():
                    if valor in ("-", "...", "X", ".."):
                        continue
                    registros.append(
                        {
                            "ano": int(ano),
                            "cod_uf": cod_uf,
                            "sigla_uf": ESTADOS_SIGLA.get(cod_uf, cod_uf),
                            "populacao": float(valor),
                        }
                    )
    return pd.DataFrame(registros)
