"""
Raspa preço por polo das marcas do grupo Ânima, usando o catálogo de cursos
cacheado em scraper/config/anima_marcas.json (ver anima_discover_courses.py).

Cada página de curso (Nuxt/Vue) embute no próprio payload da página um
array `campus`, com um preço por polo/turno. Não tem endpoint de API
separado — por isso usamos um navegador (Playwright) pra deixar o site
montar essa estrutura e ler direto de `window.useNuxtApp().payload.data`,
em vez de tentar reimplementar o formato de serialização interno do Nuxt.

Uso:
    playwright install chromium   # uma vez, se ainda não tiver
    python anima_scrape.py                 # todas as marcas do cache
    python anima_scrape.py --marca UNA      # só uma marca (teste rápido)
"""
import json
import logging
import os
import sys
import time
from datetime import date

from playwright.sync_api import sync_playwright

from db import get_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "config", "anima_marcas.json")

LOTE = 300
DELAY_ENTRE_PAGINAS_SEGUNDOS = 0.5
TIPO_PADRAO = "Privada"
FONTE = "SITE DA IES"

EXTRACT_JS = """
() => {
    const app = window.useNuxtApp();
    const keys = Object.keys(app.payload.data || {});
    const courseKey = keys.find(k => k.startsWith('course-') && !k.startsWith('course-meta') && !k.startsWith('course-page'));
    if (!courseKey) return null;
    const d = app.payload.data[courseKey];
    if (!d || !Array.isArray(d.campus)) return null;
    return { title: d.title, campus: d.campus };
}
"""


def _extrair_ofertas_ead(titulo_curso: str, slug: str, campus_list: list) -> list[dict]:
    hoje = date.today().isoformat()
    rows = []
    for campus in campus_list:
        for offer in campus.get("offers") or []:
            if offer.get("modality") != "EAD":
                continue
            if not offer.get("show_price", True):
                continue
            rows.append(
                {
                    "curso_nome": titulo_curso,
                    "curso_slug": slug,
                    "chave_curso": f"{slug}_EAD",
                    "modalidade": "EAD",
                    "turno": offer.get("turn"),
                    "tipo": TIPO_PADRAO,
                    "uf": campus.get("state"),
                    "cidade": campus.get("city"),
                    "unidade": campus.get("name"),
                    "preco_bruto": offer.get("price"),
                    "preco_desc": offer.get("special_price"),
                    "fonte": FONTE,
                    "captured_at": hoje,
                }
            )
    return rows


def main(somente_marca: str | None) -> None:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        catalogo = json.load(f)

    if somente_marca:
        catalogo = {
            dom: info for dom, info in catalogo.items() if info["marca"] == somente_marca
        }
        if not catalogo:
            logger.error("Marca '%s' nao encontrada em %s", somente_marca, CONFIG_PATH)
            return

    client = get_client()
    marca_id_by_nome = {
        row["nome"]: row["id"] for row in client.table("marcas").select("id,nome").execute().data
    }

    total_ofertas = 0
    total_paginas_com_erro = 0
    pendentes: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
            )
        )

        for dominio, info in catalogo.items():
            marca_nome = info["marca"]
            marca_id = marca_id_by_nome.get(marca_nome)
            if marca_id is None:
                logger.error("Marca '%s' (%s) nao encontrada na tabela marcas", marca_nome, dominio)
                continue

            for slug in info["slugs"]:
                url = f"https://{dominio}/cursos/graduacao/{slug}/"
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_function(
                        """() => {
                            const app = window.useNuxtApp?.();
                            const keys = Object.keys(app?.payload?.data || {});
                            return keys.some(k => k.startsWith('course-') && !k.startsWith('course-meta') && !k.startsWith('course-page'));
                        }""",
                        timeout=15000,
                    )
                    dados = page.evaluate(EXTRACT_JS)
                except Exception as e:
                    logger.error("Falha ao carregar %s: %s", url, e)
                    total_paginas_com_erro += 1
                    time.sleep(DELAY_ENTRE_PAGINAS_SEGUNDOS)
                    continue

                if not dados:
                    logger.warning("Sem dados de campus em %s", url)
                    time.sleep(DELAY_ENTRE_PAGINAS_SEGUNDOS)
                    continue

                ofertas = _extrair_ofertas_ead(dados["title"], slug, dados["campus"])
                for oferta in ofertas:
                    oferta["marca_id"] = marca_id
                pendentes.extend(ofertas)
                total_ofertas += len(ofertas)

                if len(pendentes) >= LOTE:
                    client.table("pricing_polo").upsert(
                        pendentes, on_conflict="marca_id,chave_curso,uf,unidade,captured_at"
                    ).execute()
                    pendentes = []

                time.sleep(DELAY_ENTRE_PAGINAS_SEGUNDOS)

            logger.info("Marca '%s' concluida", marca_nome)

        browser.close()

    if pendentes:
        client.table("pricing_polo").upsert(
            pendentes, on_conflict="marca_id,chave_curso,uf,unidade,captured_at"
        ).execute()

    logger.info(
        "Concluido: %d ofertas gravadas (%d paginas com erro)",
        total_ofertas,
        total_paginas_com_erro,
    )


if __name__ == "__main__":
    marca_arg = None
    if "--marca" in sys.argv:
        marca_arg = sys.argv[sys.argv.index("--marca") + 1]
    main(marca_arg)
