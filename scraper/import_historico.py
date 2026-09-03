"""
Importa a série histórica (nov/2025-jan/2026, ~16.5k linhas) de um sistema
anterior para pricing_historico. O CSV já vem agregado por
Marca + Grupo_curso + Data (uma linha por combinação), colunas:

    CALCULO_SELECIONADO_PARAMETRO_MEDIDA_PRICING,Grupo_curso,
    IM_GRUPO_EDUCACIONAL,Marca,Date

Idempotente: usa upsert (on_conflict marca_id,grupo_curso_id,captured_at),
pode rodar de novo sem duplicar.

Uso:
    python import_historico.py caminho/para/data.csv
(precisa de SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY no ambiente ou em .env)
"""
import csv
import sys
from collections import Counter

from db import get_client

LOTE = 500


def main(caminho_csv: str) -> None:
    client = get_client()

    marca_id_by_nome = {
        row["nome"]: row["id"] for row in client.table("marcas").select("id,nome").execute().data
    }
    grupo_curso_id_by_nome = {
        row["nome"]: row["id"]
        for row in client.table("grupos_curso").select("id,nome").execute().data
    }

    marcas_nao_encontradas = Counter()
    grupos_nao_encontrados = Counter()
    linhas_invalidas = 0
    rows = []

    with open(caminho_csv, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for linha in reader:
            marca_nome = (linha.get("Marca") or "").strip()
            grupo_nome = (linha.get("Grupo_curso") or "").strip()
            valor_texto = linha.get("CALCULO_SELECIONADO_PARAMETRO_MEDIDA_PRICING")
            data_texto = (linha.get("Date") or "").strip()

            marca_id = marca_id_by_nome.get(marca_nome)
            if marca_id is None:
                marcas_nao_encontradas[marca_nome] += 1
                continue

            grupo_curso_id = grupo_curso_id_by_nome.get(grupo_nome)
            if grupo_curso_id is None:
                grupos_nao_encontrados[grupo_nome] += 1

            try:
                valor = round(float(valor_texto), 2)
            except (TypeError, ValueError):
                linhas_invalidas += 1
                continue

            captured_at = data_texto.split(" ")[0]
            if not captured_at:
                linhas_invalidas += 1
                continue

            rows.append(
                {
                    "marca_id": marca_id,
                    "grupo_curso_id": grupo_curso_id,
                    "valor": valor,
                    "captured_at": captured_at,
                }
            )

    total = 0
    for i in range(0, len(rows), LOTE):
        lote = rows[i : i + LOTE]
        client.table("pricing_historico").upsert(
            lote, on_conflict="marca_id,grupo_curso_id,captured_at"
        ).execute()
        total += len(lote)
        print(f"{total}/{len(rows)} linhas gravadas")

    print(f"\nConcluído: {total} linhas importadas para pricing_historico")
    if marcas_nao_encontradas:
        print(f"\n{sum(marcas_nao_encontradas.values())} linhas ignoradas (marca não encontrada):")
        for nome, qtd in marcas_nao_encontradas.most_common():
            print(f"  - '{nome}': {qtd} linhas")
    if grupos_nao_encontrados:
        print(f"\n{sum(grupos_nao_encontrados.values())} linhas com grupo_curso não encontrado (gravadas com grupo_curso_id nulo):")
        for nome, qtd in grupos_nao_encontrados.most_common():
            print(f"  - '{nome}': {qtd} linhas")
    if linhas_invalidas:
        print(f"\n{linhas_invalidas} linhas ignoradas (valor ou data inválidos)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python import_historico.py caminho/para/data.csv")
        sys.exit(1)
    main(sys.argv[1])
