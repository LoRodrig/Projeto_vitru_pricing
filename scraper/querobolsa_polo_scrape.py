"""
Raspa a lista de campus/polos por marca no Quero Bolsa (querobolsa.com.br),
mesma plataforma do ead.com.br (README). A pagina /{slug}/campus embute o
array completo de unidades no estado inicial do Nuxt
(window.__NUXT__.state['campus-directory'].universityCampuses) -- sem
paginacao de dados, so de exibicao. Usamos Playwright so pra deixar o Nuxt
montar esse estado e ler direto do JS (o site nao tem protecao anti-bot,
mas o payload vem serializado com deduplicacao de string que nao da pra
desserializar com json.loads puro).

Diferente do grupo Anima, o Quero Bolsa nao mostra preco por campus -- so
endereco/cidade/uf. Por isso repetimos o preco por curso ja raspado do
ead.com.br (pricing_snapshots) para cada polo, como combinado com o
usuario para marcas onde o "polo" e so local de prova/apoio presencial.

Uso:
    python querobolsa_polo_scrape.py
"""
import logging
import re
import unicodedata
from datetime import date

from playwright.sync_api import sync_playwright

from db import get_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

TIPO_PADRAO = "Privada"
FONTE = "EAD.COM.BR (preço do curso) + QUEROBOLSA.COM.BR (lista de polos)"

# nome da marca -> slug no querobolsa.com.br (descoberto manualmente, testado)
MARCA_SLUG = {
    "ANHANGUERA": "anhanguera",
    "PITAGORAS": "pitagoras",
    "UNOPAR": "unopar",
    "UNIC": "unic",
    "UNIDERP": "uniderp-universidade-anhanguera-uniderp",
    "UNIME": "unime",
    "UNAMA": "unama-universidade-da-amazonia",
    "UNG": "ung",
    "UNINASSAU": "uninassau",
    "UNINORTE": "uninorte",
    "FAEL": "fael-faculdade-educacional-da-lapa",
    "ESTACIO": "estacio",
    "WYDEN": "wyden-educacional",
    "CRUZEIRO DO SUL": "unicsul-cruzeiro-do-sul",
    "SENAC SP": "senac-sp",
    "SENACRS": "senac-rs",
    "UNIJORGE": "unijorge",
    "UVA": "uva",
    "UNIP": "unip",
    "UNINOVE": "uninove",
    "UNIT": "unit-universidade-tiradentes",
    "FDPII": "dom-pedro-ii-unidom",
    "UNINTER": "uninter",
}

EXTRACT_JS = "() => window.__NUXT__?.state?.['campus-directory']?.universityCampuses || null"


def _slugify(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", sem_acento).strip("-").lower()
    return slug


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
    marca_id_by_nome = {
        row["nome"]: row["id"] for row in client.table("marcas").select("id,nome").execute().data
    }

    hoje = date.today().isoformat()
    total_marcas_ok = 0
    total_linhas = 0

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
            )
        )

        for marca_nome, slug in MARCA_SLUG.items():
            marca_id = marca_id_by_nome.get(marca_nome)
            if marca_id is None:
                logger.error("Marca '%s' nao encontrada na tabela marcas", marca_nome)
                continue

            precos = buscar_precos_por_curso(client, marca_id)
            if not precos:
                logger.warning(
                    "Marca '%s': sem preco em pricing_snapshots, pulando", marca_nome
                )
                continue

            url = f"https://querobolsa.com.br/{slug}/campus"
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_function(
                    "() => !!window.__NUXT__?.state?.['campus-directory']?.universityCampuses",
                    timeout=15000,
                )
                campuses = page.evaluate(EXTRACT_JS)
            except Exception as e:
                logger.error("Falha ao carregar %s: %s", url, e)
                continue

            if not campuses:
                logger.warning("Marca '%s': sem campus em %s", marca_nome, url)
                continue

            rows = []
            for curso_nome, valor in precos.items():
                curso_slug = _slugify(curso_nome)
                chave_curso = f"{curso_slug}_EAD"
                for campus in campuses:
                    cidade = campus.get("city")
                    uf = campus.get("state")
                    unidade = campus.get("name") or campus.get("formattedName")
                    if not (cidade and uf and unidade):
                        continue
                    rows.append(
                        {
                            "marca_id": marca_id,
                            "curso_nome": curso_nome,
                            "curso_slug": curso_slug,
                            "chave_curso": chave_curso,
                            "modalidade": "EAD",
                            "turno": None,
                            "tipo": TIPO_PADRAO,
                            "uf": uf,
                            "cidade": cidade,
                            "unidade": unidade,
                            "preco_bruto": valor,
                            "preco_desc": None,
                            "fonte": FONTE,
                            "captured_at": hoje,
                        }
                    )

            # dedup por chave unica (marca_id, chave_curso, uf, unidade, captured_at) --
            # varios campi no querobolsa repetem cidade/uf/nome (ex: mesmo predio,
            # ofertas diferentes), o upsert precisa de linhas unicas
            dedup = {}
            for r in rows:
                key = (r["chave_curso"], r["uf"], r["unidade"])
                dedup[key] = r
            rows = list(dedup.values())

            LOTE = 500
            for i in range(0, len(rows), LOTE):
                client.table("pricing_polo").upsert(
                    rows[i : i + LOTE],
                    on_conflict="marca_id,chave_curso,uf,unidade,captured_at",
                ).execute()

            total_marcas_ok += 1
            total_linhas += len(rows)
            logger.info(
                "Marca '%s': %d campus x %d cursos -> %d linhas gravadas",
                marca_nome,
                len(campuses),
                len(precos),
                len(rows),
            )

        browser.close()

    logger.info(
        "Concluido: %d linhas gravadas em %d marcas", total_linhas, total_marcas_ok
    )


if __name__ == "__main__":
    main()
