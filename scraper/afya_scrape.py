"""
Raspa a lista de polos EAD do grupo Afya (hoje só UNIGRANRIO está mapeada -
FDPII não foi confirmada no mesmo portal) e grava em pricing_polo.

A página https://ead.afya.com.br/unidades é HTML estático (Webflow + Finsweet
CMS, "render-all") com os ~52 polos já embutidos na resposta -- não precisa de
navegador. Diferente do grupo Ânima, a Afya não expõe preço por polo: todo
polo mostra a mesma mensalidade nacional. Por isso usamos o preço por curso já
raspado do ead.com.br (pricing_snapshots) e repetimos para cada polo, como
combinado com o usuário para marcas onde o "polo" é só local de prova.

Uso:
    python afya_scrape.py
"""
import logging
import re
import unicodedata
from datetime import date

import requests
from bs4 import BeautifulSoup

from db import get_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

UNIDADES_URL = "https://ead.afya.com.br/unidades"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}
TIMEOUT = 30
MARCA_NOME = "UNIGRANRIO"
TIPO_PADRAO = "Privada"
FONTE = "EAD.COM.BR (preço do curso) + SITE DA IES (lista de polos)"


def _slugify(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", sem_acento).strip("-").lower()
    return slug


def buscar_polos() -> list[dict]:
    resp = requests.get(UNIDADES_URL, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    polos = []
    for item in soup.select("div.localization-listing-item"):
        nome_el = item.select_one("h3")
        paras = item.select("div.location")[0].select("p") if item.select("div.location") else []
        if not nome_el or len(paras) < 3:
            continue
        cidade = paras[0].get_text(strip=True)
        uf = paras[2].get_text(strip=True)
        polos.append({"unidade": nome_el.get_text(strip=True), "cidade": cidade, "uf": uf})
    return polos


def buscar_precos_por_curso(client, marca_id: int) -> dict[str, float]:
    rows = (
        client.table("pricing_snapshots")
        .select("curso_nome,valor,captured_at")
        .eq("marca_id", marca_id)
        .order("captured_at", desc=True)
        .execute()
        .data
    )
    precos: dict[str, float] = {}
    for row in rows:
        precos.setdefault(row["curso_nome"], row["valor"])
    return precos


def main() -> None:
    client = get_client()
    marca = client.table("marcas").select("id,nome").eq("nome", MARCA_NOME).execute().data
    if not marca:
        logger.error("Marca '%s' nao encontrada na tabela marcas", MARCA_NOME)
        return
    marca_id = marca[0]["id"]

    polos = buscar_polos()
    logger.info("%d polos encontrados em %s", len(polos), UNIDADES_URL)
    if not polos:
        return

    precos = buscar_precos_por_curso(client, marca_id)
    if not precos:
        logger.error(
            "Sem preco por curso em pricing_snapshots para '%s' -- rode run.py antes", MARCA_NOME
        )
        return
    logger.info("%d cursos com preco conhecido (via ead.com.br)", len(precos))

    hoje = date.today().isoformat()
    rows = []
    for curso_nome, valor in precos.items():
        slug = _slugify(curso_nome)
        for polo in polos:
            rows.append(
                {
                    "marca_id": marca_id,
                    "curso_nome": curso_nome,
                    "curso_slug": slug,
                    "chave_curso": f"{slug}_EAD",
                    "modalidade": "EAD",
                    "turno": None,
                    "tipo": TIPO_PADRAO,
                    "uf": polo["uf"],
                    "cidade": polo["cidade"],
                    "unidade": polo["unidade"],
                    "preco_bruto": valor,
                    "preco_desc": None,
                    "fonte": FONTE,
                    "captured_at": hoje,
                }
            )

    LOTE = 500
    for i in range(0, len(rows), LOTE):
        client.table("pricing_polo").upsert(
            rows[i : i + LOTE], on_conflict="marca_id,chave_curso,uf,unidade,captured_at"
        ).execute()

    logger.info("Concluido: %d linhas gravadas em pricing_polo para '%s'", len(rows), MARCA_NOME)


if __name__ == "__main__":
    main()
