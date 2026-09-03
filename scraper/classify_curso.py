"""
Classifica o nome de um curso numa das 10 áreas do saber, por palavras-chave.

É uma heurística, não uma verdade absoluta: cursos que não batem com nenhuma
palavra-chave voltam None e ficam com grupo_curso_id nulo no banco, para
revisão manual (ver README, seção "revisar classificação de cursos").
"""
import unicodedata

_PALAVRAS_CHAVE = {
    "Computação e Tecnologias da Informação e Comunicação (TIC)": [
        "computacao", "software", "sistemas de informacao",
        "desenvolvimento de sistemas", "redes de computadores",
        "seguranca da informacao", "jogos digitais", "tecnologia da informacao",
        "banco de dados", "ciencia de dados", "informatica",
    ],
    "Negócios, administração e direito": [
        "administracao", "direito", "gestao", "marketing",
        "recursos humanos", "logistica", "contabeis", "contabilidade",
        "economia", "negocios imobiliarios", "comercio exterior", "financas",
        "empreendedorismo", "processos gerenciais",
    ],
    "Engenharia, produção e construção": [
        "engenharia", "arquitetura", "construcao", "edificacoes",
        "producao industrial", "manutencao industrial",
    ],
    "Saúde e bem-estar": [
        "enfermagem", "biomedicina", "nutricao", "farmacia",
        "educacao fisica", "fisioterapia", "psicologia", "estetica",
        "radiologia", "saude", "odontologia", "medicina",
    ],
    "Educação": [
        "pedagogia", "licenciatura em",
    ],
    "Agricultura, silvicultura, pesca e veterinária": [
        "agronomia", "veterinaria", "zootecnia", "agropecuaria", "agricultura",
    ],
    "Artes e humanidades": [
        "artes", "design", "filosofia", "teologia", "moda", "musica",
    ],
    "Ciências naturais, matemática e estatística": [
        "quimica", "fisica", "matematica", "biologia", "estatistica",
    ],
    "Ciências sociais, comunicação e informação": [
        "jornalismo", "publicidade", "comunicacao social", "relacoes publicas",
        "ciencias sociais", "biblioteconomia", "midias",
    ],
    "Serviços": [
        "seguranca do trabalho", "gestao ambiental", "turismo", "hotelaria",
        "gastronomia", "beleza", "estetica e cosmetica",
    ],
}


def _normalizar(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
    return sem_acento.lower()


def classificar(curso_nome: str) -> str | None:
    normalizado = _normalizar(curso_nome)
    for grupo, palavras in _PALAVRAS_CHAVE.items():
        for palavra in palavras:
            if palavra in normalizado:
                return grupo
    return None
