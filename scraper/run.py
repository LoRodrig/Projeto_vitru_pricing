"""
Roda o scraping para as marcas marcadas como piloto (ou todas, com --all) e
grava as ofertas encontradas em pricing_snapshots.

Uso:
    python run.py            # só marcas com "piloto": true
    python run.py --all      # todas as marcas cadastradas
"""
import logging
import sys
import time
from datetime import date

from classify_curso import classificar
from db import get_client
from scrape_marca import MarcaNaoEncontrada, scrape_marca

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DELAY_ENTRE_MARCAS_SEGUNDOS = 2


def main(rodar_todas: bool) -> None:
    client = get_client()

    query = client.table("marcas").select("id,nome,slug_ead,piloto")
    if not rodar_todas:
        query = query.eq("piloto", True)
    marcas = query.execute().data

    if not marcas:
        logger.warning("Nenhuma marca encontrada (rodou o seed.py?).")
        return

    grupo_curso_id_by_nome = {
        row["nome"]: row["id"]
        for row in client.table("grupos_curso").select("id,nome").execute().data
    }

    hoje = date.today().isoformat()
    total_ofertas = 0
    marcas_com_erro = []

    for marca in marcas:
        try:
            ofertas = scrape_marca(marca["slug_ead"])
        except MarcaNaoEncontrada as e:
            logger.error("Marca '%s': %s", marca["nome"], e)
            marcas_com_erro.append(marca["nome"])
            continue
        except Exception:
            logger.exception("Falha inesperada na marca '%s'", marca["nome"])
            marcas_com_erro.append(marca["nome"])
            continue

        if not ofertas:
            logger.warning("Marca '%s': nenhuma oferta encontrada", marca["nome"])
        else:
            rows = []
            for oferta in ofertas:
                grupo_curso_id = grupo_curso_id_by_nome.get(classificar(oferta.curso))
                rows.append(
                    {
                        "marca_id": marca["id"],
                        "curso_nome": oferta.curso,
                        "grupo_curso_id": grupo_curso_id,
                        "valor": oferta.valor,
                        "valor_original": oferta.valor_original,
                        "localizacao": oferta.localizacao,
                        "source_url": oferta.source_url,
                        "captured_at": hoje,
                    }
                )
            client.table("pricing_snapshots").insert(rows).execute()
            total_ofertas += len(rows)
            logger.info("Marca '%s': %d ofertas gravadas", marca["nome"], len(rows))

        time.sleep(DELAY_ENTRE_MARCAS_SEGUNDOS)

    logger.info(
        "Concluído: %d ofertas gravadas em %d marcas (%d com erro: %s)",
        total_ofertas,
        len(marcas),
        len(marcas_com_erro),
        ", ".join(marcas_com_erro) or "-",
    )


if __name__ == "__main__":
    main(rodar_todas="--all" in sys.argv)
