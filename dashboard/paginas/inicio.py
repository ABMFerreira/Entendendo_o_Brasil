"""
Página — Entendendo o Brasil (inicial)

Boas-vindas, resumo do que é a plataforma, e seleção do estado do usuário.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from db import carregar_dim_estado
from assets import CSS_GLOBAL

st.markdown(CSS_GLOBAL, unsafe_allow_html=True)

st.markdown(
    """
    <div class="entendendo-brasil-hero">
      <div class="entendendo-brasil-tag">PLATAFORMA DE INDICADORES PÚBLICOS</div>
      <h1>🇧🇷 Entendendo o Brasil</h1>
      <p>
        Indicadores públicos oficiais — economia, educação, saúde, segurança,
        meio ambiente e infraestrutura — para comparar o desempenho de cada
        estado entre si e ao longo de diferentes gestões de governo.
      </p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.subheader("Selecione seu estado para começar")

dim_estado = carregar_dim_estado()
opcoes = dict(zip(dim_estado["nome_uf"], dim_estado["sigla_uf"]))

nome_escolhido = st.selectbox("Estado", list(opcoes.keys()), index=None, placeholder="Escolha um estado...")

if nome_escolhido:
    st.session_state["sigla_uf_foco"] = opcoes[nome_escolhido]
    st.session_state["nome_uf_foco"] = nome_escolhido
    if st.button(f"Ver indicadores de {nome_escolhido} →", type="primary"):
        st.switch_page("paginas/meu_estado.py")
