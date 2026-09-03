"""
Busca as ofertas de curso EAD de uma marca no agregador ead.com.br e extrai
nome do curso, preço e instituição a partir de microdata Schema.org embutida
no HTML (nenhum JavaScript é executado — a página serve os dados prontos).
"""
import logging
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.ead.com.br/faculdades/{slug}/cursos/a-distancia-ead"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}
TIMEOUT = 20

logger = logging.getLogger(__name__)


@dataclass
class Oferta:
    curso: str
    instituicao: str
    valor: float
    valor_original: float | None
    localizacao: str | None
    source_url: str


class MarcaNaoEncontrada(Exception):
    pass


def _to_float(texto: str | None) -> float | None:
    if not texto:
        return None
    try:
        return float(texto)
    except ValueError:
        return None


def scrape_marca(slug: str) -> list[Oferta]:
    url = BASE_URL.format(slug=slug)
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)

    if resp.status_code == 404:
        raise MarcaNaoEncontrada(f"slug '{slug}' não existe em {url}")
    resp.raise_for_status()

    final_url = resp.url
    soup = BeautifulSoup(resp.text, "lxml")

    ofertas: list[Oferta] = []
    for course_el in soup.select('[itemtype="https://schema.org/Course"]'):
        name_el = course_el.select_one('[itemprop="name"]')
        provider_el = course_el.select_one(
            '[itemtype="https://schema.org/CollegeOrUniversity"] [itemprop="name"]'
        )
        offer_el = course_el.select_one('[itemtype="https://schema.org/Offer"]')
        if not name_el or not offer_el:
            continue

        price_el = offer_el.select_one('[itemprop="price"]')
        valor = _to_float(price_el.get("content") if price_el else None)
        if valor is None:
            continue

        instance_el = course_el.select_one('[itemtype="https://schema.org/CourseInstance"]')
        location_el = (
            instance_el.select_one('[itemtype="https://schema.org/Place"] [itemprop="name"]')
            if instance_el
            else None
        )

        ofertas.append(
            Oferta(
                curso=name_el.get("content", "").strip(),
                instituicao=(provider_el.get("content") if provider_el else "").strip(),
                valor=valor,
                valor_original=None,
                localizacao=location_el.get("content") if location_el else None,
                source_url=final_url,
            )
        )

    if not ofertas:
        logger.warning("Nenhuma oferta encontrada para slug '%s' (%s)", slug, final_url)

    return ofertas
