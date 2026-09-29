# Ficha Técnica dos Indicadores — v1

Documento de referência única (single source of truth) para os 10 indicadores do MVP.
Cada indicador deve ser atualizado aqui antes de qualquer alteração no ETL correspondente.

Status ETL: 🟢 pronto | 🟡 em desenvolvimento | ⚪ pendente

---

## 1. PIB per capita 🟢
- **Definição**: Produto Interno Bruto total dividido pela população residente estimada.
- **Unidade**: R$ por habitante/ano.
- **Periodicidade**: Anual.
- **Granularidade**: Estado (UF).
- **Fonte**: IBGE — duas tabelas SIDRA combinadas (o IBGE não publica PIB per capita por UF como variável pronta):
  - PIB total: tabela 5938 (pesquisa "PIB dos Municípios"), variável 37, Mil Reais.
  - População: tabela 6579 (pesquisa "Estimativas de População"), variável 9324, Pessoas.
- **Cálculo**: `pib_per_capita = (pib_mil_reais * 1000) / populacao` — calculado no próprio ETL (`ibge_sidra_pib.py`), não fornecido pronto pela fonte.
- **Observações**: Tabela 6784 (que parecia natural pelo nome "PIB per capita") NÃO serve — pertence à pesquisa "Contas Nacionais Anuais" e só tem dado a nível Brasil (N1), não por estado. Descoberta feita via inspeção de metadados (`diagnostico_ibge.py`). **Defasagem confirmada: dado disponível só até 2023** (tabela 5938 tem `"fim": 2023"` nos metadados) — normal para Contas Regionais, que levam ~2 anos para fechar, diferente de dados de execução orçamentária (SICONFI), que chegam a 2025. Usar `--anos 2015-2023` como intervalo confiável; reconferir com `diagnostico_ibge.py 5938` a cada atualização.

## 2. Índice de Gini 🟢
- **Definição**: Medida de desigualdade de renda domiciliar per capita (0 = igualdade perfeita, 1 = desigualdade máxima).
- **Periodicidade**: Anual.
- **Granularidade**: Estado.
- **Fonte**: IBGE/SIDRA, tabela 7435 (PNAD Contínua Anual), variável 10681. Nível N3 confirmado, sem classificações extras — tabela direta (ano x localidade x valor). Script: `ibge_gini.py` (sem credencial).
- **Observações**: Validado por plausibilidade — valores na faixa 0,45-0,58 em 2015, com Distrito Federal no topo (0,581), consistente com a desigualdade extrema conhecida do DF (alto escalão de governo convivendo com cidades-satélite de renda baixa).

## 3. IDHM 🟢
- **Definição**: Índice de Desenvolvimento Humano Municipal/Estadual (renda, longevidade, educação).
- **Periodicidade**: Decenal (Censo) — **não é anual**, ver ressalva abaixo.
- **Granularidade**: Estado.
- **Fonte**: Base dos Dados (BigQuery) — `basedosdados.mundo_onu_adh.uf`, que já traz tratado o Atlas do Desenvolvimento Humano (PNUD/Ipea/FJP). Também traz os 3 subíndices (`idhm_e` educação, `idhm_l` longevidade, `idhm_r` renda) — útil para mostrar qual dimensão puxa o índice de um estado para baixo. Script: `idhm_uf.py`.
- **⚠️ Limitação estrutural (não é bug)**: o IDHM só existe para anos de Censo — **1991, 2000 e 2010**, confirmado (81 linhas = 27 estados × 3 anos). Existe uma versão mais recente baseada na PNAD Contínua (2022, 2024 — "Radar IDHM" do Atlas Brasil), mas não está na Base dos Dados; exigiria raspar atlasbrasil.org.br diretamente. Fora do escopo desta primeira versão — considerar como melhoria futura.
- **Observações**: Validado por plausibilidade — DF no topo (0,616 em 1991), Maranhão entre os mais baixos (0,357), consistente com o padrão de desigualdade regional já visto nos outros indicadores.

## 4. Despesa por função (saúde/educação) 🟢
- **Definição**: Despesa liquidada por função de governo (Saúde, Educação), valor total do estado no ano.
- **Unidade**: R$.
- **Periodicidade**: Anual (consolidado a partir de dados bimestrais).
- **Granularidade**: Estado.
- **Fonte**: Base dos Dados (BigQuery) — `basedosdados.br_me_siconfi.uf_despesas_funcao`.
- **Filtros usados**: `estagio_bd = 'Despesas Liquidadas'`, `id_conta_bd IN ('3.10.000', '3.12.000')` (linhas de total por função, não soma manual de subfunções).
- **Histórico**: Tentamos a API pública do SICONFI diretamente primeiro; ela ignorava parâmetros de filtro sem dar erro (ver `etl/diagnostico_siconfi*.py`), então pivotamos para a Base dos Dados, que também será usada nos indicadores 5, 7, 8 e 9.
- **Observações**: "Despesas Liquidadas" foi escolhida por ser a fase mais adequada para medir execução orçamentária real entre estados (diferente de "Empenhadas" = só compromisso, e "Pagas" = pode atrasar por restos a pagar). Documentar essa escolha metodológica de forma visível no site. **Dado confirmado completo (27/27 estados) até 2025**; 2026 deve estar parcial (ano corrente, declarações ainda em andamento) — reconferir a cobertura por ano antes de cada atualização do site.

## 5. Taxa de desemprego / emprego formal 🟢
- **Definição**: Dois componentes complementares — taxa de desocupação (pesquisa amostral) e estoque de vínculos formais ativos (registro administrativo).
- **Periodicidade**: Anual (desocupação = média dos 4 trimestres; emprego formal = posição em 31/12).
- **Granularidade**: Estado.
- **Componente 1 — Taxa de desocupação**: IBGE/SIDRA, tabela 6396 (PNAD Contínua Trimestral), variável 4099, classificação Sexo=Total. Calculamos a **média dos 4 trimestres do ano** como taxa anual, para não escolher um trimestre arbitrário como representativo. Script: `ibge_taxa_desocupacao.py` (sem credencial, só IBGE).
- **Componente 2 — Emprego formal**: Base dos Dados (BigQuery) — `br_me_rais.microdados_vinculos`, filtrando `vinculo_ativo_3112 = '1'` (vínculo ativo em 31/12 — confirmado por inspeção: campo só assume '1' ou '0'). Consulta agregada direto no SQL (`COUNT` + `GROUP BY`) para não trazer os microdados brutos ao cliente — importante porque a tabela tem 250 GB. Calculamos também vínculos por 1.000 habitantes, reaproveitando a população do indicador 1. Script: `rais_emprego_formal.py`.
- **Observações**: Valores validados por plausibilidade — DF (sede de governo, alta renda) com 433 vínculos/mil hab. em 2015 vs. Maranhão com 104, consistente com a desigualdade regional conhecida.

## 6. Área de desmatamento ⚪
- **Definição**: Área desmatada NO ANO (incremento anual, km²), detectada por satélite.
- **Periodicidade**: Anual.
- **Granularidade**: Estado.
- **Fonte**: Base dos Dados (BigQuery) — `br_inpe_prodes.municipio_bioma`, sem `sigla_uf` direto (join com `br_bd_diretorios_brasil.municipio`).
- **⚠️ Achado importante**: a coluna `desmatado` da fonte é ÁREA ACUMULADA até o ano, não o incremento anual — descoberto porque o cálculo ingênuo (soma direta) dava valores impossíveis (ex.: Bahia com >260 mil km² desmatados EM UM ANO). Corrigido calculando a diferença ano a ano por município+bioma via `LAG()` no SQL, descartando o primeiro ano de cada série (sem par anterior) e exigindo anos consecutivos (sem buracos). Script: `prodes_desmatamento.py`.
- **Limitação de cobertura**: o PRODES monitora a Amazônia Legal desde 1988; outros biomas entraram no monitoramento sistemático bem mais tarde — anos antigos fora da Amazônia Legal podem ter cobertura incompleta.
- **Observações**: Validado por plausibilidade — Amazonas 688 km² e Bahia (fronteira agrícola do Cerrado) 2.199 km² em 2015, DF quase zero (território pequeno).

## 7. Mortalidade infantil 🟢
- **Definição**: Óbitos de menores de 1 ano por 1.000 nascidos vivos.
- **Periodicidade**: Anual.
- **Granularidade**: Estado.
- **Fonte final**: IBGE/SIDRA, tabela 7362 (pesquisa "Projeção da População"), variável 1940. **Não** é o cálculo direto SIM/SINASC (esse fica só como componente bruto em `sim_sinasc_saude.py`, não publicar).
- **Por que essa fonte resolve o problema de sub-registro**: a série da tabela 7362 não vem de contar registros brutos — o IBGE pareia SIM/SINASC com a pesquisa de Registro Civil e aplica a técnica de captura-recaptura para estimar os óbitos/nascimentos reais, incluindo os não registrados. Validado por comparação: valores agora ficam na faixa esperada (~9-23/mil em 2015, com Norte/Nordeste acima da média — condizente com o padrão conhecido), diferente da subestimativa uniforme que tínhamos antes.
- **⚠️ Restrição de uso importante**: a tabela cobre 2000-2060 numa única série contínua, MAS anos além do último ano com dado real observado (~2023, conforme a metodologia da Revisão 2024) são **projeção demográfica pura, não fato**. Usar o indicador só até 2023; anos posteriores não devem ser exibidos como "dado", ou devem ser claramente rotulados como "projeção" se um dia quisermos mostrar cenários futuros (fora do escopo do MVP).
- **Observações**: Query técnica precisa de duas classificações (Sexo=Total, Ano=valor específico) porque a "periodicidade" formal da tabela é fixa em 2018 (edição), e o ano real do dado é uma classificação interna — detalhe descoberto por inspeção, documentado no script `ibge_mortalidade_infantil.py`.

## 8. IDEB 🟢
- **Definição**: Índice de Desenvolvimento da Educação Básica (combina fluxo escolar e proficiência), rede estadual.
- **Periodicidade**: Bienal.
- **Granularidade**: Estado (rede estadual).
- **Fonte**: Base dos Dados (BigQuery) — `br_inep_ideb.uf`, filtrando `rede = 'estadual'`.
- **Estrutura**: a tabela vem quebrada por etapa de ensino — não existe um "IDEB médio do estado" único (a própria metodologia oficial do IDEB não combina etapas). Trazemos 3 linhas por estado/ano: fundamental anos iniciais, fundamental anos finais, e médio. Script: `ideb_uf.py`.
- **Observações**: Validado por plausibilidade — valores na faixa nacional conhecida (ex.: Acre 5,5 nos anos iniciais, 3,5 no médio — etapa média historicamente mais baixa, padrão nacional).

## 9. Taxa de homicídios 🟢
- **Definição**: Óbitos por agressão (homicídios) por 100.000 habitantes.
- **Periodicidade**: Anual.
- **Granularidade**: Estado.
- **Fonte**: Base dos Dados (BigQuery) — `br_ms_sim.microdados` (numerador) + população reaproveitada do CSV do indicador 1 (IBGE, tabela 6579, já validada).
- **Critério**: `causa_basica` (CID-10) entre X85 e Y09 (capítulo "Agressões", definição padrão da OMS para homicídio). Não inclui sequelas de agressão (Y87.1) nem lesões de intenção indeterminada (Y10-Y34) — escolha conservadora.
- **Observações**: Mesmo script do indicador 7 (`sim_sinasc_saude.py`), já que os dois vêm da mesma tabela de óbitos. Depende de `ibge_sidra_pib.py` já ter sido rodado antes (para ter o CSV de população disponível). **Ressalva menor** (mesma família de problema do indicador 7, mas de escala bem menor): óbitos por causa externa passam por perícia médico-legal, então o sub-registro tende a ser bem inferior ao de óbitos neonatais — mantemos 🟢, mas vale reavaliar se a comparação entre estados ficar estranha.

## 10. % domicílios com saneamento adequado 🟢
- **Definição**: Percentual da população urbana atendida por abastecimento de água e coleta de esgoto.
- **Periodicidade**: Anual.
- **Granularidade**: Estado.
- **Fonte**: Base dos Dados (BigQuery) — `br_mdr_snis.municipio_agua_esgoto` (dado administrativo dos prestadores de serviço), agregado por estado com média ponderada pela população urbana.
- **⚠️ Achado importante**: a primeira tentativa (dividir soma de população atendida por soma de população urbana) deu estados com MAIS de 100% de atendimento (ex.: Bahia 108%) — logicamente impossível, causado por descompasso entre duas colunas de população da fonte. Corrigido usando os índices já calculados oficialmente pelo próprio SNIS por município (`indice_atendimento_total_agua`, `indice_coleta_esgoto`), com média ponderada pela população — mais confiável do que recalcular a divisão manualmente. Script: `snis_saneamento.py`.
- **Observações**: Validado por plausibilidade — DF no topo (99% água), Amapá no fim (35%), consistente com o padrão de infraestrutura regional conhecido. Ainda vale documentar no site a diferença de metodologia frente à PNAD Contínua (administrativa vs. amostral), como previsto originalmente — não implementamos a fonte secundária (PNAD) nesta rodada, pode ser um complemento futuro.

---

## Resumo de vias de acesso

| Via de acesso | Indicadores | Complexidade ETL |
|---|---|---|
| API IBGE/SIDRA (REST, direta) | 1, 2, 5 | Baixa |
| API SICONFI (REST, direta) | 4 | Baixa-média |
| Base dos Dados (BigQuery) | 5, 7, 8, 9 | Média (requer client BigQuery + conta Google Cloud) |
| Atlas Brasil (download) | 3 | Média |
| TerraBrasilis/INPE (download) | 6 | Média |
| SNIS (download/portal) | 10 | Média |

**Próximo passo depois do MVP com IBGE+SICONFI**: configurar acesso à Base dos Dados (é gratuito, mas exige criar um projeto no Google Cloud — decisão simples, faço o guia quando chegarmos lá).
