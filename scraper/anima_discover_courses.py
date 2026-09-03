"""
Descobre o catálogo de cursos de cada marca do grupo Ânima (as que rodam a
mesma plataforma Nuxt com preço por polo embutido na página do curso) e
grava em scraper/config/anima_marcas.json.

Isso roda raramente (só quando uma marca lança/remove um curso) — o
resultado fica versionado no repositório, então scraper/anima_scrape.py
nunca precisa redescobrir os cursos, só ler esse cache.

Uso:
    playwright install chromium   # uma vez, se ainda não tiver
    python anima_discover_courses.py
"""
import json
import os

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "config", "anima_marcas.json")

# domínio -> nome da marca (deve bater com marcas.json)
DOMINIOS = {
    "portal.anhembi.br": "UAM",
    "www.una.br": "UNA",
    "www.ibmr.br": "IBMR",
    "www.usjt.br": "SAO JUDAS",
    "www.unifacs.br": "UNIFACS",
    "www.uniritter.edu.br": "UNIRITTER",
    "www.unisul.br": "UNISUL",
    "www.unisociesc.com.br": "UNISOCIESC",
    "www.fadergs.edu.br": "FADERGS",
    "www.unifg.edu.br": "UNIFG",
    "www.unp.br": "UNP",
}

EXTRACT_JS = """
() => {
    const app = window.useNuxtApp();
    const keys = Object.keys(app.payload.data || {});
    const coursesKey = keys.find(k => k.startsWith('Courses-'));
    if (!coursesKey) return null;
    return app.payload.data[coursesKey].results.map(c => c.slug);
}
"""


def main() -> None:
    resultado = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
            )
        )
        for dominio, marca in DOMINIOS.items():
            url = f"https://{dominio}/cursos/graduacao/"
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_function(
                    "() => !!window.useNuxtApp?.().payload?.data", timeout=15000
                )
                slugs = page.evaluate(EXTRACT_JS)
                if not slugs:
                    print(f"AVISO: nao achei lista de cursos em {url}")
                    continue
                resultado[dominio] = {"marca": marca, "slugs": sorted(set(slugs))}
                print(f"{dominio} ({marca}): {len(slugs)} cursos")
            except Exception as e:
                print(f"ERRO em {url}: {e}")
        browser.close()

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2, sort_keys=True)
    print(f"\nGravado em {CONFIG_PATH}")


if __name__ == "__main__":
    main()
