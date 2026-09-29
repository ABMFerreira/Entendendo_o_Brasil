"""
Diagnóstico — API do SICONFI (Tesouro Nacional).

Uso:
    python diagnostico_siconfi.py

Testa, em sequência:
1. /entes — confirma o formato do id_ente para São Paulo (esperado: "35")
2. /anexos-rreo — lista os nomes reais dos anexos do RREO aceitos pela API
3. /rreo SEM o filtro no_anexo — mostra os primeiros registros crus, para
   vermos os nomes de campos e de anexos que a API realmente devolve
"""
import requests

BASE_URL = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt"

print("=== 1. /entes (São Paulo, esfera Estadual) ===\n")
resp = requests.get(f"{BASE_URL}/entes", params={"co_esfera": "E", "co_uf": "35"}, timeout=30)
print(f"HTTP {resp.status_code}")
print(resp.text[:1500])

print("\n=== 2. /anexos-rreo (nomes de anexo aceitos) ===\n")
resp2 = requests.get(f"{BASE_URL}/anexos-rreo", timeout=30)
print(f"HTTP {resp2.status_code}")
print(resp2.text[:2000])

print("\n=== 3. /rreo SEM no_anexo, São Paulo, 2022, período 6 ===\n")
resp3 = requests.get(
    f"{BASE_URL}/rreo",
    params={"an_exercicio": 2022, "nr_periodo": 6, "co_esfera": "E", "id_ente": "35", "limit": 20},
    timeout=30,
)
print(f"HTTP {resp3.status_code}")
print(resp3.text[:3000])
