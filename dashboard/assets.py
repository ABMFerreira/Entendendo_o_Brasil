"""
Assets visuais compartilhados: CSS com as cores da bandeira do Brasil (em vez
de uma foto de fundo, para evitar qualquer risco de direitos autorais) e
busca dinâmica da bandeira de cada estado no Wikimedia Commons (acervo
público) — em vez de links fixos para os 27 estados, que quebrariam
silenciosamente se algum nome de arquivo estivesse errado.
"""
import streamlit as st
import requests

VERDE = "#009639"
AMARELO = "#FEDD00"
AZUL = "#002776"

CSS_GLOBAL = f"""
<style>
.entendendo-brasil-hero {{
    background: linear-gradient(135deg, {VERDE} 0%, {AMARELO} 55%, {AZUL} 100%);
    padding: 2.5rem 2rem;
    border-radius: 14px;
    color: white;
    text-shadow: 0 1px 4px rgba(0,0,0,0.45);
    margin-bottom: 1.5rem;
}}
.entendendo-brasil-hero h1 {{
    font-size: 2.4rem;
    margin: 0 0 0.4rem 0;
    font-weight: 800;
}}
.entendendo-brasil-hero p {{
    font-size: 1.05rem;
    max-width: 620px;
    margin: 0;
    opacity: 0.95;
}}
.entendendo-brasil-tag {{
    display: inline-block;
    background: {AZUL};
    color: white;
    padding: 0.15rem 0.6rem;
    border-radius: 6px;
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.03em;
    margin-bottom: 0.6rem;
}}
</style>
"""


@st.cache_data(ttl=86400)
def buscar_url_bandeira(nome_estado: str) -> str | None:
    """
    Busca a bandeira do estado no Wikimedia Commons via API de busca, em vez
    de usar um link fixo por estado (que poderia quebrar silenciosamente).
    Retorna None se não encontrar — nesse caso, o app simplesmente não
    mostra bandeira nenhuma, em vez de mostrar um ícone de imagem quebrada.
    """
    try:
        resp = requests.get(
            "https://commons.wikimedia.org/w/api.php",
            params={
                "action": "query",
                "format": "json",
                "list": "search",
                "srsearch": f"Bandeira do estado {nome_estado} Brasil filetype:svg",
                "srnamespace": 6,  # namespace "File:"
                "srlimit": 1,
            },
            timeout=5,
            headers={"User-Agent": "PlataformaIndicadoresBR/1.0"},
        )
        resultados = resp.json().get("query", {}).get("search", [])
        if not resultados:
            return None
        titulo_arquivo = resultados[0]["title"]  # ex: "File:Bandeira do estado de São Paulo.svg"
        nome_arquivo = titulo_arquivo.split(":", 1)[1]
        return f"https://commons.wikimedia.org/wiki/Special:FilePath/{nome_arquivo}"
    except Exception:
        return None
