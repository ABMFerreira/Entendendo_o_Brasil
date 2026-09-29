# Plataforma de Indicadores Públicos — Brasil

Plataforma freemium para gestores públicos compararem indicadores entre estados
e entre gestões/mandatos, com camada de analítica avançada (fase 2).

## Status atual: ETL + modelagem de dados concluídos — próximo passo é o dashboard

**Banco de dados no Supabase com 4 tabelas, todas escritas e validadas:**
- `dim_estado` (27 UFs)
- `dim_indicador` (catálogo dos 12 sub-indicadores)
- `fato_indicador` (9.955 linhas — todos os valores dos 10 indicadores)
- `dim_governador` (110 linhas — governadores eleitos por estado/ciclo 2010-2022,
  com 2 casos sinalizados para revisão manual — ver nota abaixo)

| # | Indicador | Fonte | Cobertura temporal |
|---|---|---|---|
| 1 | PIB per capita | IBGE/SIDRA | 2015-2023 |
| 2 | Índice de Gini | IBGE/SIDRA | 2012-2025 |
| 3 | IDHM | Base dos Dados | Só 1991/2000/2010 (decenal) |
| 4 | Despesa por função (todas) | Base dos Dados | 2015-2025 |
| 5 | Desemprego/emprego formal | IBGE + Base dos Dados | 2015-2023 |
| 6 | Área de desmatamento | Base dos Dados | 2015-2023 (Amazônia Legal com cobertura mais longa) |
| 7 | Mortalidade infantil | IBGE/SIDRA | 2015-2023 (usar só até aqui — resto é projeção) |
| 8 | IDEB | Base dos Dados | Bienal, 2015-2023 |
| 9 | Taxa de homicídios | Base dos Dados | 2015-2023 |
| 10 | Saneamento (água/esgoto) | Base dos Dados | 2015-2023 |

## ⚠️ Nota pendente: 2 estados com sucessão por cassação (ciclo 2014-2018)

Amazonas e Tocantins tiveram o governador eleito em 2014 CASSADO pelo TSE
(compra de votos/caixa 2) e substituído por outra pessoa, por processos e
datas de transição que os relatos públicos descrevem de forma não totalmente
consistente entre si. A tabela `dim_governador` mantém as 2 pessoas de cada
caso, marcadas com `requer_revisao_manual = True` e sem período de mandato
calculado — **não usar esses 2 estados na análise de "impacto por gestão"
do ciclo 2014-2018 até essa pesquisa histórica ser feita manualmente.**
Todos os outros 26 estados × 4 ciclos (104 registros) estão limpos.


- [x] Escopo de 10 indicadores definido e documentado (`docs/ficha_tecnica_indicadores.md`)
- [x] Acesso à Base dos Dados (BigQuery) configurado
- [x] **Todos os 10 ETLs escritos e validados com dados reais**
- [x] **Schema consolidado (dim_estado, dim_indicador, fato_indicador) escrito no Supabase**
- [ ] Tabela de governadores/mandatos por estado — script pronto (`governadores_uf.py`), ainda não subida ao Supabase
- [ ] Dashboard (Streamlit) — próximo passo

## Como rodar tudo localmente (ordem importa em alguns casos)

```
pip install -r requirements.txt --user
cd etl

# 1 — PIB per capita (IBGE, sem credencial) — RODAR PRIMEIRO
#     (indicadores 9 e 5-parte-RAIS reaproveitam a população deste CSV)
python ibge_sidra_pib.py --anos 2015-2023

# 2 — Índice de Gini (IBGE, sem credencial)
python ibge_gini.py --anos 2015-2023

# 3 — IDHM (Base dos Dados)
python idhm_uf.py --credenciais ..\credenciais\bigquery-key.json --project SEU_PROJECT_ID

# 4 — Despesa por função, todas as funções (Base dos Dados)
python siconfi_despesas_funcao.py --credenciais ..\credenciais\bigquery-key.json --project SEU_PROJECT_ID --ano-inicio 2015 --ano-fim 2025

# 5 — Desemprego (IBGE, sem credencial) + Emprego formal (Base dos Dados)
python ibge_taxa_desocupacao.py --anos 2015-2023
python rais_emprego_formal.py --credenciais ..\credenciais\bigquery-key.json --project SEU_PROJECT_ID --ano-inicio 2015 --ano-fim 2023

# 6 — Desmatamento (Base dos Dados)
python prodes_desmatamento.py --credenciais ..\credenciais\bigquery-key.json --project SEU_PROJECT_ID --ano-inicio 2015 --ano-fim 2023

# 7 — Mortalidade infantil, série oficial corrigida (IBGE, sem credencial)
python ibge_mortalidade_infantil.py --anos 2015-2023

# 8 — IDEB (Base dos Dados)
python ideb_uf.py --credenciais ..\credenciais\bigquery-key.json --project SEU_PROJECT_ID --ano-inicio 2015 --ano-fim 2023

# 9 — Taxa de homicídios (Base dos Dados) — precisa do passo 1 já feito
python sim_sinasc_saude.py --credenciais ..\credenciais\bigquery-key.json --project SEU_PROJECT_ID --ano-inicio 2015 --ano-fim 2023

# 10 — Saneamento (Base dos Dados)
python snis_saneamento.py --credenciais ..\credenciais\bigquery-key.json --project SEU_PROJECT_ID --ano-inicio 2015 --ano-fim 2023
```

Os CSVs de saída vão para `../data/`.

## Lições aprendidas ao longo da fase de ETL (vale reler antes de modelar o banco)

- **Nunca confie no nome de uma tabela/variável só pelo nome** — a tabela 6784 do IBGE
  parecia ser "PIB per capita" mas só tinha dado a nível Brasil. Sempre inspecione
  metadados antes de escrever um ETL novo (`diagnostico_ibge.py` para IBGE;
  `INFORMATION_SCHEMA.TABLES`/`COLUMNS` para BigQuery).
- **APIs de governo sem contrato formal (sem Swagger) são um risco real** — a API direta
  do SICONFI ignorava filtros silenciosamente, sem erro. A Base dos Dados (BigQuery)
  resolveu isso na maioria dos casos, incluindo indicadores que originalmente pareciam
  exigir download manual de arquivo (IDHM, desmatamento, saneamento).
- **Sempre valide a plausibilidade dos números contra uma referência conhecida antes de
  aceitar um indicador como "pronto"** — foi assim que pegamos: sub-registro no
  indicador 7, área acumulada (não incremento) no indicador 6, e taxas acima de 100%
  no indicador 10. Um número plausível mas tecnicamente errado é mais perigoso que um
  erro óbvio, porque passa despercebido.
- **Quando uma fonte primária (microdados) tiver viés conhecido, procure primeiro se já
  existe uma série oficial corrigida ou um índice pré-calculado** antes de tentar
  corrigir na mão — funcionou tanto para mortalidade infantil (série de projeção do
  IBGE) quanto para saneamento (índices já calculados do próprio SNIS).
- **Cuidado com colunas "acumuladas" vs. "incremento"** em séries temporais de
  satélite/monitoramento — não assuma que o valor bruto é o incremento do período.
- **Reaproveite dados já validados entre indicadores** — a população do indicador 1
  alimenta os indicadores 5 (parte RAIS) e 9, evitando buscar de novo.

## Dashboard (Streamlit)

Três páginas:
- `dashboard/app.py` — roteador (define os títulos das páginas na navegação).
- `dashboard/paginas/inicio.py` — página inicial: boas-vindas + seleção de estado.
- `dashboard/paginas/meu_estado.py` — análise do indicador escolhido, com:
  - Linha do estado em foco, **média da região** e **média do Brasil** por padrão.
  - Opção de adicionar estados específicos para comparação.
  - Despesa por função com alternância entre valor absoluto e **% do gasto total do estado**.
  - Faixas sombreadas no gráfico indicando qual **governo estava em exercício** em cada período (via `dim_governador`).
  - Bandeira do estado (busca dinâmica no Wikimedia Commons).
- `dashboard/paginas/analise_cruzada.py` — comparação entre **gasto e indicadores de resultado**,
  com múltiplos estados/regiões/Brasil, múltiplas funções de despesa, múltiplos indicadores,
  controle de **defasagem em anos** (gasto de N anos atrás x indicador de hoje), e uma
  tabela de **correlação (Pearson)** — associação estatística, não causalidade.
  IDHM e IDEB ficam fora dessa página (têm subdivisões internas que complicariam os
  filtros) — continuam disponíveis em "Meu Estado".

**⚠️ Passo obrigatório antes de rodar**: a tabela `dim_estado` ganhou uma
coluna nova (`regiao`), necessária para a média regional. Se você já tinha
rodado `consolidar_supabase.py` antes desta atualização, rode de novo:
```
cd etl
python consolidar_supabase.py
```
(usa os CSVs que você já tem — não precisa rodar os ETLs de novo)

**Rodar localmente**:
```
pip install -r requirements.txt --user
cd dashboard
python -m streamlit run app.py
```
Usa o mesmo `.env` (raiz do projeto) que os scripts de ETL.

**Deploy gratuito (Streamlit Community Cloud)**:
1. Suba o projeto para um repositório no GitHub (o `.gitignore` já protege
   `.env` e `credenciais/`).
2. Em [share.streamlit.io](https://share.streamlit.io), conecte o repositório
   e aponte para `dashboard/app.py`.
3. Em **Settings → Secrets** do app, cole:
   ```
   SUPABASE_DB_URL = "postgresql://postgres.xxxxx:SENHA@aws-0-...pooler.supabase.com:5432/postgres"
   ```

## Estrutura do projeto

```
plataforma-indicadores-br/
├── docs/
│   └── ficha_tecnica_indicadores.md      # definição, fonte e metodologia de cada indicador
├── dashboard/
│   ├── app.py                            # roteador (st.navigation, define títulos das páginas)
│   ├── db.py                             # acesso a dados compartilhado entre páginas
│   ├── assets.py                         # CSS (cores do Brasil) + busca de bandeira estadual
│   └── paginas/
│       ├── inicio.py                     # página inicial (boas-vindas + seleção de estado)
│       ├── meu_estado.py                 # análise por estado (indicador, região, governo)
│       └── analise_cruzada.py            # gasto x indicadores, com defasagem e correlação
├── etl/
│   ├── common.py                         # códigos de estados, helpers
│   ├── ibge_sidra_pib.py                 # indicador 1
│   ├── ibge_gini.py                      # indicador 2
│   ├── idhm_uf.py                        # indicador 3
│   ├── siconfi_despesas_funcao.py        # indicador 4 (todas as funções orçamentárias)
│   ├── ibge_taxa_desocupacao.py          # indicador 5 (parte 1/2 — desocupação)
│   ├── rais_emprego_formal.py            # indicador 5 (parte 2/2 — emprego formal)
│   ├── prodes_desmatamento.py            # indicador 6
│   ├── ibge_mortalidade_infantil.py      # indicador 7 (série oficial corrigida — usar esta)
│   ├── ideb_uf.py                        # indicador 8
│   ├── sim_sinasc_saude.py               # indicador 9 + componente bruto do 7 (não publicar o 7 bruto)
│   ├── snis_saneamento.py                # indicador 10
│   ├── governadores_uf.py                # dim_governador (ciclos 2010-2022, TSE)
│   ├── consolidar_supabase.py            # junta os 11 CSVs e sobe as 4 tabelas para o Supabase
│   ├── diagnostico_ibge.py               # ferramenta reutilizável p/ inspecionar tabelas IBGE
│   ├── diagnostico_siconfi.py            # histórico: investigação da API direta do SICONFI
│   └── diagnostico_siconfi2.py           # histórico: idem
├── data/                                 # saída dos CSVs (gerado, não versionar)
├── credenciais/                          # chave da conta de serviço BigQuery (não versionar)
├── .env                                  # SUPABASE_DB_URL (não versionar — copie de .env.example)
└── requirements.txt
```

## Próximos passos (retomando o plano de 12 semanas)

1. **Resolver a pendência de Amazonas/Tocantins** (ciclo 2014-2018) com pesquisa
   histórica dedicada, antes de usar esses 2 estados na análise por gestão.
2. **Iniciar o dashboard em Streamlit** — primeira versão com comparação entre
   estados por indicador/ano, consultando direto o Supabase.
3. **Comparação entre gestões/mandatos** — já temos `dim_governador`; falta a
   lógica no dashboard que cruza `fato_indicador` com o período de mandato
   (ex.: "como evoluiu o indicador X do início ao fim de cada governo").
4. Camada de analítica avançada (correlações, tendências, avaliação de
   impacto) — fase seguinte do plano, depois do dashboard básico funcionar.
