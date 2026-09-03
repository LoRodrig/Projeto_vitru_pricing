"""
Gera marcas.json e grupos_curso.json a partir da planilha de referência.

Roda-se uma vez (ou sempre que a lista de marcas/grupos mudar na planilha).
O .xlsx de origem NÃO faz parte do repositório (é dado interno) — passe o
caminho dele via argumento ou variável de ambiente SOURCE_XLSX.

Uso:
    python build_config.py "C:\\caminho\\para\\data.xlsx"
"""
import json
import os
import re
import sys
import unicodedata

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))


def slugify(nome: str) -> str:
    nfkd = unicodedata.normalize("NFKD", nome)
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
    slug = sem_acento.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


def main(xlsx_path: str) -> None:
    grupo_marca = pd.read_excel(xlsx_path, sheet_name="Grupo e Marca")
    grupo_curso = pd.read_excel(xlsx_path, sheet_name="Grupo dos cursos")

    marcas = []
    for _, row in grupo_marca.iterrows():
        nome = str(row["Marca"]).strip()
        marcas.append(
            {
                "nome": nome,
                "grupo_educacional": str(row["IM_GRUPO_EDUCACIONAL"]).strip(),
                "slug_ead": slugify(nome),
                "piloto": nome in {"ESTACIO", "ANHANGUERA", "UNINTER", "UNICESUMAR", "UNIP"},
            }
        )
    marcas.sort(key=lambda m: m["nome"])

    grupos = [str(v).strip() for v in grupo_curso["Grupo_curso"].dropna().tolist()]

    with open(os.path.join(HERE, "marcas.json"), "w", encoding="utf-8") as f:
        json.dump(marcas, f, ensure_ascii=False, indent=2)

    with open(os.path.join(HERE, "grupos_curso.json"), "w", encoding="utf-8") as f:
        json.dump(grupos, f, ensure_ascii=False, indent=2)

    print(f"OK: {len(marcas)} marcas, {len(grupos)} grupos de curso gerados.")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("SOURCE_XLSX")
    if not path:
        print("Passe o caminho do .xlsx como argumento ou defina SOURCE_XLSX.")
        sys.exit(1)
    main(path)
