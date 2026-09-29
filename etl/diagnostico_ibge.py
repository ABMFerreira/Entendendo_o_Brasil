"""
Diagnóstico — inspeciona os metadados de uma tabela do IBGE/SIDRA para descobrir
os IDs corretos de variáveis, classificações e níveis territoriais suportados.

Uso:
    python diagnostico_ibge.py 6784
    python diagnostico_ibge.py 5938
"""
import sys

import requests

TABELA = sys.argv[1] if len(sys.argv) > 1 else "6784"

print(f"=== Metadados da tabela {TABELA} ===\n")
resp = requests.get(f"https://servicodados.ibge.gov.br/api/v3/agregados/{TABELA}/metadados", timeout=30)
print(f"HTTP {resp.status_code}")
meta = resp.json()

print(f"Nome: {meta.get('nome')}")
print(f"Pesquisa: {meta.get('pesquisa')}")
print(f"Nível territorial: {meta.get('nivelTerritorial')}")
print(f"Periodicidade: {meta.get('periodicidade')}\n")

print("--- TODAS as variáveis (id: nome) ---")
for v in meta.get("variaveis", []):
    print(f"  {v['id']}: {v['nome']} ({v.get('unidade')})")

print("\n--- Variáveis que parecem ser 'per capita' ou 'população' ---")
for v in meta.get("variaveis", []):
    nome_lower = v["nome"].lower()
    if "per capita" in nome_lower or "população" in nome_lower or "populacao" in nome_lower:
        print(f"  >>> ID {v['id']}: {v['nome']} ({v.get('unidade')})")

print("\n--- Classificações (se houver) ---")
for c in meta.get("classificacoes", []):
    print(f"  {c['id']}: {c['nome']}")
    for cat in c.get("categorias", []):
        print(f"      categoria {cat['id']}: {cat['nome']}")

