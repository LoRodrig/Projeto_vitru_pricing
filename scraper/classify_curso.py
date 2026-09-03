"""
Classifica o nome de um curso em uma das categorias de negócio usadas
internamente (scraper/config/grupos_curso.json), por palavras-chave.

É uma heurística reconstruída sem acesso à regra original que gerou essas
categorias — não é uma verdade absoluta. Cursos que não batem com nenhuma
palavra-chave caem em "Outros" (nunca ficam nulos). Revise periodicamente
(ver README, seção "revisar classificação de cursos") e ajuste as listas
de palavras-chave abaixo conforme encontrar classificações erradas.
"""
import unicodedata

OUTROS = "Outros"

# Ordem importa: categorias mais específicas primeiro, "Tecnologo" e
# "Outros" por último como fallback.
_PALAVRAS_CHAVE = {
    "Eng. Civil": [
        "engenharia civil", "edificacoes", "construcao civil",
    ],
    "Eng. Produção + Eng.Software": [
        "engenharia de producao", "engenharia de software",
        "ciencia da computacao", "engenharia da computacao",
        "sistemas de informacao", "analise e desenvolvimento de sistemas",
        "desenvolvimento de sistemas", "redes de computadores",
        "seguranca da informacao", "ciencia de dados", "banco de dados",
        "jogos digitais", "tecnologia da informacao", "informatica",
        "engenharia mecatronica", "engenharia eletrica",
        "engenharia mecanica", "engenharia de controle e automacao",
        "engenharia de producao industrial",
    ],
    "Adm + Contábeis": [
        "administracao", "contabeis", "contabilidade", "gestao comercial",
        "gestao empresarial", "gestao financeira", "gestao de negocios",
        "gestao publica", "gestao de rh", "marketing",
        "recursos humanos", "logistica", "economia",
        "negocios imobiliarios", "comercio exterior", "financas",
        "empreendedorismo", "processos gerenciais", "secretariado",
    ],
    "Saúde - Enfermagem e Biomedicina": [
        "enfermagem", "biomedicina",
    ],
    "Ed. Física": [
        "educacao fisica",
    ],
    "Estética e Cosmética": [
        "estetica e cosmetica", "estetica", "cosmetica",
    ],
    "Pedagogia - Educação": [
        "pedagogia", "licenciatura em",
    ],
    "Letras": [
        "letras", "literatura",
    ],
    "Serviço Social": [
        "servico social",
    ],
}

# Fallback: cursos de "Tecnólogo" que não bateram em nenhuma categoria
# específica acima (ex.: "Tecnólogo em Gestão Ambiental").
_PALAVRA_TECNOLOGO = "tecnolog"


def _normalizar(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
    return sem_acento.lower()


def classificar(curso_nome: str) -> str:
    normalizado = _normalizar(curso_nome)
    for grupo, palavras in _PALAVRAS_CHAVE.items():
        for palavra in palavras:
            if palavra in normalizado:
                return grupo

    if _PALAVRA_TECNOLOGO in normalizado:
        return "Tecnologo"

    return OUTROS
