"""
Carrega/atualiza as tabelas de referência (grupos_educacionais, grupos_curso,
marcas) no Supabase a partir de scraper/config/*.json.

Idempotente: pode rodar de novo sempre que a lista de marcas mudar.

Uso:
    python seed.py
(precisa de SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY no ambiente ou em .env)
"""
import json
import os

from db import get_client

HERE = os.path.dirname(os.path.abspath(__file__))


def _load_json(name: str):
    with open(os.path.join(HERE, "config", name), encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    client = get_client()
    marcas = _load_json("marcas.json")
    grupos_curso = _load_json("grupos_curso.json")

    grupos_educacionais = sorted({m["grupo_educacional"] for m in marcas})
    client.table("grupos_educacionais").upsert(
        [{"nome": g} for g in grupos_educacionais], on_conflict="nome"
    ).execute()
    print(f"grupos_educacionais: {len(grupos_educacionais)} ok")

    client.table("grupos_curso").upsert(
        [{"nome": g} for g in grupos_curso], on_conflict="nome"
    ).execute()
    print(f"grupos_curso: {len(grupos_curso)} ok")

    grupo_id_by_nome = {
        row["nome"]: row["id"]
        for row in client.table("grupos_educacionais").select("id,nome").execute().data
    }

    marcas_payload = [
        {
            "nome": m["nome"],
            "slug_ead": m["slug_ead"],
            "grupo_educacional_id": grupo_id_by_nome[m["grupo_educacional"]],
            "piloto": m["piloto"],
        }
        for m in marcas
    ]
    client.table("marcas").upsert(marcas_payload, on_conflict="nome").execute()
    print(f"marcas: {len(marcas_payload)} ok")


if __name__ == "__main__":
    main()
