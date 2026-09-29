"""
Página — Meu Estado

Mostra um indicador ao longo do tempo para o estado escolhido, comparado por
padrão com a média da região e a média do Brasil, com opção de adicionar
outros estados específicos. Para despesa por função, permite alternar entre
valor absoluto e % do gasto total do estado. Mostra também faixas sombreadas
indicando qual governo estava em exercício em cada período.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from db import carregar_dados_indicador, carregar_dim_estado, carregar_dim_indicador, mandatos_do_estado

st.set_page_config(page_title="Meu Estado — Indicadores Públicos", page_icon="📍", layout="wide")

dim_estado = carregar_dim_estado()
dim_indicador = carregar_dim_indicador()

# --- Estado em foco: vem da página inicial (session_state) ou é escolhido aqui ---
if "sigla_uf_foco" not in st.session_state:
    st.info("Escolha um estado para começar.")
    opcoes = dict(zip(dim_estado["nome_uf"], dim_estado["sigla_uf"]))
    nome_escolhido = st.selectbox("Estado", list(opcoes.keys()), index=None, placeholder="Escolha um estado...")
    if not nome_escolhido:
        st.stop()
    st.session_state["sigla_uf_foco"] = opcoes[nome_escolhido]
    st.session_state["nome_uf_foco"] = nome_escolhido

sigla_foco = st.session_state["sigla_uf_foco"]
nome_foco = st.session_state["nome_uf_foco"]
regiao_foco = dim_estado.loc[dim_estado["sigla_uf"] == sigla_foco, "regiao"].iloc[0]

st.title(f"📍 {nome_foco}")
if st.button("← Trocar de estado"):
    del st.session_state["sigla_uf_foco"]
    st.switch_page("app.py")

# --- Filtros ---
col_filtros, col_grafico = st.columns([1, 3])

with col_filtros:
    st.subheader("Filtros")

    nomes_indicadores = dim_indicador["nome"].tolist()
    nome_indicador_escolhido = st.selectbox("Indicador", nomes_indicadores)
    linha_indicador = dim_indicador[dim_indicador["nome"] == nome_indicador_escolhido].iloc[0]
    id_indicador = linha_indicador["id_indicador"]
    unidade = linha_indicador["unidade"]

    st.caption(f"**Fonte**: {linha_indicador['fonte']}")
    st.caption(f"**Periodicidade**: {linha_indicador['periodicidade']}")

    dados_completos = carregar_dados_indicador(id_indicador)

    dimensoes_disponiveis = sorted(d for d in dados_completos["dimensao"].unique() if d)
    dimensao_escolhida = None
    if dimensoes_disponiveis:
        dimensao_escolhida = st.selectbox("Detalhe", dimensoes_disponiveis)
        dados_dimensao = dados_completos[dados_completos["dimensao"] == dimensao_escolhida]
    else:
        dados_dimensao = dados_completos

    # --- Caso especial: despesa por função em % do total do estado ---
    mostrar_percentual = False
    if id_indicador == "4_despesa_funcao":
        modo = st.radio("Visualização", ["Valor absoluto", "% do gasto total do estado"])
        mostrar_percentual = modo == "% do gasto total do estado"

    if mostrar_percentual:
        total_uf_ano = (
            dados_completos.groupby(["ano", "sigla_uf"])["valor"].sum().reset_index(name="total_uf")
        )
        dados = dados_dimensao.merge(total_uf_ano, on=["ano", "sigla_uf"], how="left")
        dados["valor"] = (dados["valor"] / dados["total_uf"]) * 100
        dados = dados.drop(columns="total_uf")
        unidade_exibida = "%"
    else:
        dados = dados_dimensao
        unidade_exibida = unidade

    outros_estados_disponiveis = sorted(s for s in dados["sigla_uf"].unique() if s != sigla_foco)
    estados_extras = st.multiselect(
        "Comparar com outros estados específicos (opcional)", outros_estados_disponiveis
    )

# --- Monta as séries do gráfico: estado foco, média região, média Brasil, extras ---
series = []

foco_df = dados[dados["sigla_uf"] == sigla_foco][["ano", "valor"]].copy()
foco_df["serie"] = nome_foco
series.append(foco_df)

dados_com_regiao = dados.merge(dim_estado[["sigla_uf", "regiao"]], on="sigla_uf", how="left")

media_regiao_df = (
    dados_com_regiao[dados_com_regiao["regiao"] == regiao_foco]
    .groupby("ano")["valor"]
    .mean()
    .reset_index()
)
media_regiao_df["serie"] = f"Média {regiao_foco}"
series.append(media_regiao_df)

media_brasil_df = dados.groupby("ano")["valor"].mean().reset_index()
media_brasil_df["serie"] = "Média Brasil"
series.append(media_brasil_df)

for uf_extra in estados_extras:
    nome_extra = dim_estado.loc[dim_estado["sigla_uf"] == uf_extra, "nome_uf"].iloc[0]
    extra_df = dados[dados["sigla_uf"] == uf_extra][["ano", "valor"]].copy()
    extra_df["serie"] = nome_extra
    series.append(extra_df)

dados_grafico = pd.concat(series, ignore_index=True)

# --- Gráfico ---
with col_grafico:
    if dados_grafico.empty or dados_grafico["valor"].isna().all():
        st.warning("Nenhum dado encontrado para essa combinação de filtros.")
    else:
        titulo = nome_indicador_escolhido
        if dimensao_escolhida:
            titulo += f" — {dimensao_escolhida}"

        fig = px.line(
            dados_grafico.sort_values(["serie", "ano"]),
            x="ano",
            y="valor",
            color="serie",
            markers=True,
            title=titulo,
            labels={"ano": "Ano", "valor": unidade_exibida, "serie": ""},
        )
        # destaca a linha do estado em foco
        fig.update_traces(line=dict(width=4), selector=dict(name=nome_foco))

        # --- Faixas sombreadas indicando qual governo estava em exercício ---
        mandatos = mandatos_do_estado(sigla_foco)
        cores_faixa = ["rgba(100,100,100,0.06)", "rgba(100,100,100,0.12)"]
        for i, mandato in enumerate(mandatos.itertuples()):
            fig.add_vrect(
                x0=mandato.inicio_mandato.year,
                x1=mandato.fim_mandato.year,
                fillcolor=cores_faixa[i % 2],
                line_width=0,
                annotation_text=f"{mandato.nome_candidato.split()[0]} ({mandato.sigla_partido})",
                annotation_position="top left",
                annotation_font_size=10,
            )

        st.plotly_chart(fig, use_container_width=True)

        if mandatos.empty:
            st.caption(
                "⚠️ Não há dados de mandatos disponíveis para este estado no período "
                "(ou o(s) período(s) está(ão) marcado(s) para revisão manual — ver ficha técnica)."
            )

        with st.expander("Ver tabela de dados"):
            st.dataframe(dados_grafico.sort_values(["ano", "serie"]).reset_index(drop=True), use_container_width=True)
