"""
Ponto de entrada do dashboard. Usa st.navigation (em vez da descoberta
automática de pasta pages/) para poder dar um título customizado a cada
página na barra lateral — "Entendendo o Brasil" em vez do nome do arquivo.
"""
import streamlit as st

st.set_page_config(page_title="Entendendo o Brasil", page_icon="🇧🇷", layout="wide")

pagina_inicio = st.Page("paginas/inicio.py", title="Entendendo o Brasil", icon="🏠", default=True)
pagina_estado = st.Page("paginas/meu_estado.py", title="Meu Estado", icon="📍")
pagina_cruzada = st.Page("paginas/analise_cruzada.py", title="Análise Cruzada", icon="🔀")

navegacao = st.navigation([pagina_inicio, pagina_estado, pagina_cruzada])
navegacao.run()
