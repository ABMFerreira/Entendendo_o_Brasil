"""
Página — Análise Cruzada (Gasto x Indicadores)

Permite selecionar múltiplos estados (e/ou regiões, e/ou o Brasil como um
todo), múltiplas funções de despesa e múltiplos indicadores de resultado,
com um controle de defasagem em anos — para investigar perguntas do tipo
"uma queda no gasto em saúde antecede um aumento na mortalidade infantil?".

Dois painéis empilhados (mesmo eixo X = ano), em vez de eixos Y duplicados
no mesmo gráfico — mais legível quando há várias combinações de linhas.

IDHM e IDEB ficam FORA do seletor de indicadores aqui — eles têm
subdivisões internas (subíndices/etapas) que tornariam os filtros
combinatoriamente complexos nesta tela. Continuam disponíveis na página
"Meu Estado".

A correlação exibida é um coeficiente de Pearson simples — mede associação
linear, NÃO causalidade. Serve como um número de apoio à leitura visual do
gráfico, não como prova de impacto.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import plotly.express as px
import streamlit as st
from plotly.subplots import make_subplots
import plotly.graph_objects as go
import statsmodels.formula.api as smf

from db import carregar_dados_indicador, carregar_dim_estado, carregar_dim_indicador, expandir_com_agregados

dim_estado = carregar_dim_estado()
dim_indicador = carregar_dim_indicador()

st.title("🔀 Análise Cruzada — Gasto x Indicadores")
st.caption(
    "Compare a evolução do gasto em uma ou mais funções com um ou mais indicadores de resultado, "
    "com opção de defasagem em anos (ex.: gasto de anos atrás x indicador de hoje)."
)

# --- Entidades disponíveis: estados + regiões + Brasil ---
entidades_estados = sorted(dim_estado["nome_uf"].tolist())
entidades_regioes = sorted("Região " + r for r in dim_estado["regiao"].unique())
entidades_disponiveis = entidades_estados + entidades_regioes + ["Brasil (média)"]

default_entidades = ["Brasil (média)"]
if "nome_uf_foco" in st.session_state:
    default_entidades = [st.session_state["nome_uf_foco"], "Brasil (média)"]

# --- Dados de despesa por função (base para o seletor de funções) ---
despesa_completa = carregar_dados_indicador("4_despesa_funcao")
funcoes_disponiveis = sorted(despesa_completa["dimensao"].unique())

# --- Indicadores elegíveis (fora despesa, IDHM e IDEB — ver docstring) ---
indicadores_elegiveis = dim_indicador[~dim_indicador["id_indicador"].isin(["4_despesa_funcao", "3_idhm", "8_ideb"])]

with st.form("filtros_analise_cruzada"):
    entidades_escolhidas = st.multiselect(
        "Estados / Regiões / Brasil", entidades_disponiveis, default=default_entidades
    )

    col_a, col_b = st.columns(2)
    with col_a:
        funcoes_escolhidas = st.multiselect(
            "Função(ões) de despesa", funcoes_disponiveis, default=funcoes_disponiveis[:1]
        )
        modo_despesa = st.radio("Despesa em", ["Valor absoluto (R$)", "% do gasto total do estado"], horizontal=True)
    with col_b:
        indicadores_escolhidos = st.multiselect(
            "Indicador(es) de resultado", indicadores_elegiveis["nome"].tolist()
        )
        defasagem = st.slider(
            "Defasagem (anos) — gasto de N anos antes vs. indicador de hoje", 0, 5, 0
        )

    st.form_submit_button("Aplicar filtros", type="primary")

if not entidades_escolhidas or not funcoes_escolhidas or not indicadores_escolhidos:
    st.info("Escolha ao menos 1 estado/região, 1 função de despesa e 1 indicador para ver o gráfico.")
    st.stop()

# --- Prepara despesa (% calculado ANTES de agregar por região/Brasil) ---
if modo_despesa == "% do gasto total do estado":
    total_uf_ano = despesa_completa.groupby(["ano", "sigla_uf"])["valor"].sum().reset_index(name="total_uf")
    despesa_pct = despesa_completa.merge(total_uf_ano, on=["ano", "sigla_uf"], how="left")
    despesa_pct["valor"] = (despesa_pct["valor"] / despesa_pct["total_uf"]) * 100
    despesa_base = despesa_pct.drop(columns="total_uf")
    unidade_despesa = "%"
else:
    despesa_base = despesa_completa
    unidade_despesa = "R$"

despesa_filtrada = despesa_base[despesa_base["dimensao"].isin(funcoes_escolhidas)]
despesa_expandida = expandir_com_agregados(despesa_filtrada, dim_estado)
despesa_expandida = despesa_expandida[despesa_expandida["entidade"].isin(entidades_escolhidas)]
despesa_expandida["serie"] = despesa_expandida["entidade"] + " — " + despesa_expandida["dimensao"]
# desloca a despesa para frente no tempo, para alinhar visualmente com o
# indicador que ela pode ter influenciado anos depois
despesa_expandida["ano_exibido"] = despesa_expandida["ano"] + defasagem

# --- Prepara indicadores (um por vez, empilhando os escolhidos) ---
partes_indicador = []
for nome_ind in indicadores_escolhidos:
    linha = indicadores_elegiveis[indicadores_elegiveis["nome"] == nome_ind].iloc[0]
    dados_ind = carregar_dados_indicador(linha["id_indicador"])
    dados_ind = dados_ind[dados_ind["dimensao"] == ""]  # só a série "geral" (estes indicadores não têm subdivisão)
    expandida = expandir_com_agregados(dados_ind, dim_estado)
    expandida = expandida[expandida["entidade"].isin(entidades_escolhidas)]
    expandida["serie"] = expandida["entidade"] + " — " + nome_ind
    expandida["indicador_nome"] = nome_ind
    expandida["unidade"] = linha["unidade"]
    partes_indicador.append(expandida)

indicador_expandido = pd.concat(partes_indicador, ignore_index=True) if partes_indicador else pd.DataFrame()

# --- Gráfico: dois painéis empilhados, mesmo eixo X ---
fig = make_subplots(
    rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
    subplot_titles=(f"Despesa ({unidade_despesa})", "Indicador(es) de resultado"),
)

for serie_nome, grupo in despesa_expandida.groupby("serie"):
    fig.add_trace(
        go.Scatter(x=grupo["ano_exibido"], y=grupo["valor"], mode="lines+markers", name=serie_nome, legendgroup="despesa"),
        row=1, col=1,
    )

for serie_nome, grupo in indicador_expandido.groupby("serie"):
    fig.add_trace(
        go.Scatter(x=grupo["ano"], y=grupo["valor"], mode="lines+markers", name=serie_nome, legendgroup="indicador"),
        row=2, col=1,
    )

fig.update_xaxes(title_text="Ano", row=2, col=1)
fig.update_layout(height=650, legend=dict(orientation="h", yanchor="bottom", y=-0.35))

st.plotly_chart(fig, use_container_width=True)

if defasagem > 0:
    st.caption(
        f"A curva de despesa está deslocada {defasagem} ano(s) para frente — o ponto exibido no "
        f"ano X representa o gasto que ocorreu em X−{defasagem}, alinhado para comparação visual "
        "com o indicador do ano X."
    )

# --- Tabela de correlação (Pearson) por combinação entidade x função x indicador ---
st.subheader("Correlação (Pearson)")
st.caption(
    "Mede associação linear entre as duas séries, considerando a defasagem escolhida acima. "
    "NÃO indica causalidade — use como apoio à leitura do gráfico, não como prova de impacto."
)

linhas_correlacao = []
for entidade in entidades_escolhidas:
    for funcao in funcoes_escolhidas:
        despesa_serie = despesa_expandida[
            (despesa_expandida["entidade"] == entidade) & (despesa_expandida["dimensao"] == funcao)
        ][["ano_exibido", "valor"]].rename(columns={"ano_exibido": "ano", "valor": "valor_despesa"})

        for nome_ind in indicadores_escolhidos:
            indicador_serie = indicador_expandido[
                (indicador_expandido["entidade"] == entidade) & (indicador_expandido["indicador_nome"] == nome_ind)
            ][["ano", "valor"]].rename(columns={"valor": "valor_indicador"})

            merged = despesa_serie.merge(indicador_serie, on="ano", how="inner")
            n = len(merged)
            if n >= 3:
                r = merged["valor_despesa"].corr(merged["valor_indicador"])
                linhas_correlacao.append(
                    {"Estado/Região": entidade, "Função": funcao, "Indicador": nome_ind, "Correlação (r)": round(r, 3), "Anos comparados": n}
                )

if linhas_correlacao:
    st.dataframe(pd.DataFrame(linhas_correlacao), use_container_width=True, hide_index=True)
else:
    st.caption("Anos insuficientes em comum entre as séries escolhidas para calcular correlação (mínimo: 3).")


# =============================================================================
# ANÁLISE MAIS RIGOROSA: REGRESSÃO COM EFEITOS FIXOS
# =============================================================================
st.divider()
st.subheader("🔬 Análise mais rigorosa: regressão com efeitos fixos")

with st.expander("O que é isso, e por que a correlação simples acima não basta"):
    st.markdown(
        """
        A correlação simples da tabela acima pode enganar: um estado pode melhorar um
        indicador e aumentar gasto ao mesmo tempo só porque está **ficando mais rico
        de forma geral** (mais arrecadação, mais de tudo) — não necessariamente porque
        aquele gasto específico causou a melhora.

        A regressão abaixo usa **efeitos fixos de estado e de ano**: ela controla
        automaticamente por características que não mudam de um estado para o outro
        (geografia, histórico, cultura política) e por choques que afetam **todos os
        estados no mesmo ano** (uma recessão nacional, uma mudança de política federal).
        O que sobra é uma estimativa mais confiável — ainda assim **não é prova de
        causalidade**, mas é um padrão bem mais rigoroso que a correlação simples, e é
        o tipo de método usado em avaliação séria de política pública (IPEA, Banco
        Mundial, etc.).

        **Usa sempre os 27 estados**, mesmo que você tenha filtrado poucos para o
        gráfico acima — o método precisa da variação do painel completo para funcionar.
        """
    )

rodar_regressao = st.checkbox("Rodar regressão com efeitos fixos")

if rodar_regressao:
    despesa_painel_completo = despesa_base[despesa_base["dimensao"].isin(funcoes_escolhidas)].copy()
    despesa_painel_completo["ano_exibido"] = despesa_painel_completo["ano"] + defasagem

    linhas_regressao = []
    for funcao in funcoes_escolhidas:
        despesa_funcao_df = despesa_painel_completo[despesa_painel_completo["dimensao"] == funcao][
            ["sigla_uf", "ano_exibido", "valor"]
        ].rename(columns={"ano_exibido": "ano", "valor": "valor_despesa"})

        for nome_ind in indicadores_escolhidos:
            linha_ind = indicadores_elegiveis[indicadores_elegiveis["nome"] == nome_ind].iloc[0]
            dados_ind_raw = carregar_dados_indicador(linha_ind["id_indicador"])
            dados_ind_raw = dados_ind_raw[dados_ind_raw["dimensao"] == ""][["sigla_uf", "ano", "valor"]].rename(
                columns={"valor": "valor_indicador"}
            )

            painel = despesa_funcao_df.merge(dados_ind_raw, on=["sigla_uf", "ano"], how="inner")
            n_estados = painel["sigla_uf"].nunique()
            n_obs = len(painel)

            resultado_linha = {
                "Função": funcao,
                "Indicador": nome_ind,
                "N observações": n_obs,
                "N estados": n_estados,
            }

            if n_obs < 30 or n_estados < 5:
                resultado_linha["Efeito estimado"] = None
                resultado_linha["Valor-p"] = None
                resultado_linha["Interpretação"] = "Dados insuficientes para rodar a regressão com confiança"
            else:
                try:
                    modelo = smf.ols(
                        "valor_indicador ~ valor_despesa + C(sigla_uf) + C(ano)", data=painel
                    ).fit(cov_type="cluster", cov_kwds={"groups": painel["sigla_uf"]})
                    coef = modelo.params["valor_despesa"]
                    p_valor = modelo.pvalues["valor_despesa"]

                    resultado_linha["Efeito estimado"] = round(coef, 5)
                    resultado_linha["Valor-p"] = round(p_valor, 4)
                    if p_valor < 0.05:
                        direcao = "reduz" if coef < 0 else "aumenta"
                        resultado_linha["Interpretação"] = (
                            f"Estatisticamente significativo (p<0,05): aumento no gasto associado a {direcao} o indicador"
                        )
                    else:
                        resultado_linha["Interpretação"] = "Não significativo — não há evidência estatística suficiente"
                except Exception as e:
                    resultado_linha["Efeito estimado"] = None
                    resultado_linha["Valor-p"] = None
                    resultado_linha["Interpretação"] = f"Não foi possível estimar (erro técnico: {type(e).__name__})"

            linhas_regressao.append(resultado_linha)

    st.dataframe(pd.DataFrame(linhas_regressao), use_container_width=True, hide_index=True)

    st.caption(
        "⚠️ **Mesmo um resultado 'estatisticamente significativo' aqui não é prova definitiva de "
        "causalidade** — ainda pode haver fatores não observados que mudam ao longo do tempo "
        "*dentro* de cada estado (não capturados pelos efeitos fixos) e explicam os dois ao mesmo "
        "tempo, e a causalidade pode em tese correr no sentido inverso (o indicador melhorando "
        "gera mais arrecadação, que permite mais gasto). Use como um sinal mais forte para "
        "investigar, não como uma conclusão fechada."
    )
