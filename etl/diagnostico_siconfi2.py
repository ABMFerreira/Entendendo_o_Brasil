"""
Diagnóstico v2 — API do SICONFI: testa variações de parâmetros para descobrir
a combinação correta de id_ente / co_esfera / nr_periodo.

Uso:
    python diagnostico_siconfi2.py
"""
import requests

BASE_URL = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt"


def get(path, params):
    resp = requests.get(f"{BASE_URL}/{path}", params=params, timeout=30)
    try:
        dados = resp.json()
        count = dados.get("count", "N/A")
        items = dados.get("items", [])
    except Exception:
        count, items = "ERRO_PARSE", []
    return resp.status_code, count, items


print("=== 1. /entes filtrando por an_exercicio + co_esfera=E ===\n")
status, count, items = get("entes", {"an_exercicio": 2022, "co_esfera": "E"})
print(f"HTTP {status} | count={count}")
for item in items[:5]:
    print(" ", item)

print("\n=== 2. Mesma consulta, sem an_exercicio (só co_esfera=E) ===\n")
status, count, items = get("entes", {"co_esfera": "E"})
print(f"HTTP {status} | count={count}")
for item in items[:5]:
    print(" ", item)

print("\n=== 3. Varrendo nr_periodo 1-6 para São Paulo, 2022, esfera E ===\n")
for periodo in range(1, 7):
    status, count, items = get(
        "rreo",
        {"an_exercicio": 2022, "nr_periodo": periodo, "co_esfera": "E", "id_ente": "35"},
    )
    print(f"  período {periodo}: HTTP {status} | count={count}")

print("\n=== 4. Mesmo teste do item 3, mas para 2021 (ano fechado) ===\n")
for periodo in range(1, 7):
    status, count, items = get(
        "rreo",
        {"an_exercicio": 2021, "nr_periodo": periodo, "co_esfera": "E", "id_ente": "35"},
    )
    print(f"  período {periodo}: HTTP {status} | count={count}")

print("\n=== 5. Tentando sem co_esfera, só id_ente + an_exercicio + nr_periodo=6 (2021) ===\n")
status, count, items = get("rreo", {"an_exercicio": 2021, "nr_periodo": 6, "id_ente": "35"})
print(f"HTTP {status} | count={count}")
if items:
    print("Primeiro item bruto:", items[0])
