"""Deterministic query analysis and reranking for the veterinary RAG.

Version 0.14 adds an explicit domain gate before embeddings are generated. The
local language model is never asked to decide whether a question belongs to the
veterinary domain. This keeps the routing reproducible, auditable and cheap.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from typing import Iterable


CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    'vaccination': ('vacuna', 'vacunacion', 'rabia', 'antirrabica', 'moquillo', 'parvovirus'),
    'travel': ('viajar', 'viaje', 'pasaporte', 'frontera', 'entrada', 'salir de espana', 'union europea', 'ue'),
    'parasites': ('parasito', 'desparasitar', 'gusano', 'lombriz', 'pulga', 'garrapata', 'leishmania', 'dirofilaria'),
    'nutrition': ('peso', 'obesidad', 'adelgazar', 'engordar', 'alimentacion', 'dieta', 'condicion corporal'),
    'senior_care': ('senior', 'mayor', 'geriatrico', 'envejecimiento', 'edad avanzada'),
    'renal': ('renal', 'rinon', 'creatinina', 'sdma', 'enfermedad renal'),
    'vector_borne': ('vector', 'mosquito', 'flebotomo', 'leishmania', 'babesia', 'ehrlichia', 'anaplasma'),
    'procedures': ('tramite', 'documentacion', 'certificado', 'microchip', 'pasaporte'),
    'clinical_history': ('historial', 'paciente', 'casos', 'recurrente', 'diagnostico', 'eventos'),
}

COUNTRY_KEYWORDS: dict[str, tuple[str, ...]] = {
    'ES': ('espana', 'espanol', 'madrid', 'peninsula'),
    'EU': ('union europea', 'ue', 'europa', 'francia', 'portugal', 'italia', 'alemania'),
    'INT': ('fuera de la ue', 'tercer pais', 'internacional', 'extracomunitario'),
}

SPECIES_KEYWORDS: dict[str, tuple[str, ...]] = {
    'dog': ('perro', 'perra', 'canino', 'cachorro'),
    'cat': ('gato', 'gata', 'felino', 'gatito'),
}

URGENCY_KEYWORDS: tuple[str, ...] = (
    'no respira', 'dificultad respiratoria', 'respira con dificultad', 'convulsion',
    'convulsiones', 'inconsciente', 'desmayo', 'sangrado abundante', 'hemorragia',
    'atropello', 'intoxicacion', 'veneno', 'abdomen hinchado', 'no puede orinar',
    'paralisis', 'golpe de calor', 'temperatura muy alta', 'vomita sangre',
)

# Terms that provide direct evidence that a query belongs to the domain. Generic
# routing words such as "historial" are deliberately excluded because they also
# occur in unrelated contexts.
VETERINARY_TERMS: tuple[str, ...] = (
    'veterinario', 'veterinaria', 'clinica veterinaria', 'mascota', 'animal',
    'perro', 'perra', 'canino', 'cachorro', 'gato', 'gata', 'felino', 'gatito',
    'vacuna', 'vacunacion', 'rabia', 'parasito', 'desparasitar', 'pulga',
    'garrapata', 'mosquito', 'leishmania', 'dirofilaria', 'otitis', 'dermatitis',
    'alergia', 'renal', 'rinon', 'creatinina', 'sdma', 'orina', 'analitica',
    'sangre', 'diagnostico', 'tratamiento', 'sintoma', 'enfermedad', 'dolor',
    'respiratorio', 'respiracion', 'digestivo', 'diarrea', 'vomito', 'articular',
    'cojera', 'braquicefalico', 'esterilizado', 'microchip', 'pasaporte',
    'condicion corporal', 'peso', 'senior', 'geriatrico', 'nutricion', 'dieta',
)

PET_OPERATION_TERMS: tuple[str, ...] = (
    'plan', 'pago', 'pagar', 'cuota', 'importe', 'pendiente', 'renovacion',
    'renovar', 'servicio', 'prestacion', 'aviso', 'vencimiento', 'caduca', 'cita',
)

CLINICAL_INTENT_TERMS: tuple[str, ...] = (
    'paciente', 'pacientes', 'historial', 'historiales', 'caso', 'casos',
    'episodio', 'episodios', 'evento', 'eventos', 'consulta', 'consultas',
    'seguimiento', 'recurrente', 'repetido', 'laboratorio', 'revision',
)

# Explicit evidence of a different domain. Negative evidence only blocks a query
# when it is not accompanied by strong veterinary evidence, so a question such
# as "mi gato mordio un cable del ordenador" remains in scope.
OUT_OF_DOMAIN_TERMS: dict[str, tuple[str, ...]] = {
    'computing': (
        'ordenador', 'computadora', 'windows', 'linux', 'macos', 'impresora',
        'placa base', 'placas base', 'procesador', 'memoria ram', 'tarjeta grafica', 'servidor',
        'base de datos', 'docker', 'kubernetes', 'router wifi', 'programacion',
    ),
    'general_knowledge': (
        'capital de', 'presidente de', 'rio mas largo', 'montana mas alta',
        'segunda guerra mundial', 'premio nobel', 'tabla periodica',
    ),
    'finance': ('hipoteca', 'bolsa de valores', 'bitcoin', 'factura electrica', 'impuesto'),
    'sports': ('liga de futbol', 'champions', 'mundial de futbol', 'resultado del partido'),
}

STOPWORDS = {
    'que', 'como', 'cuando', 'donde', 'para', 'por', 'con', 'sin', 'una', 'uno',
    'unos', 'unas', 'del', 'las', 'los', 'esta', 'este', 'esto', 'tiene', 'puede',
    'debo', 'necesito', 'mi', 'mis', 'su', 'sus', 'mascota', 'animal', 'informacion',
}


@dataclass(slots=True)
class QueryProfile:
    """Deterministic interpretation used to guide retrieval and reporting."""

    normalised_question: str
    categories: list[str]
    species: list[str]
    countries: list[str]
    keywords: list[str]
    urgent: bool
    urgency_matches: list[str]
    scope: str
    in_domain: bool
    domain_reason: str
    domain_positive_matches: list[str]
    domain_negative_matches: list[str]

    def filters(self) -> dict[str, list[str] | bool | str]:
        return {
            'categories': self.categories,
            'species': self.species,
            'countries': self.countries,
            'urgent': self.urgent,
            'scope': self.scope,
            'in_domain': self.in_domain,
            'domain_reason': self.domain_reason,
            'domain_positive_matches': self.domain_positive_matches,
            'domain_negative_matches': self.domain_negative_matches,
        }


def normalise(text: str) -> str:
    """Lowercase, remove accents and collapse punctuation for robust matching."""
    decomposed = unicodedata.normalize('NFKD', text.casefold())
    ascii_text = ''.join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r'[^a-z0-9]+', ' ', ascii_text).strip()


def _contains_term(text: str, value: str) -> bool:
    """Match complete normalised words or phrases, never arbitrary substrings."""
    term = normalise(value)
    if not term:
        return False
    if ' ' not in term and len(term) >= 4:
        pattern = rf'(?<![a-z0-9]){re.escape(term)}(?:s|es)?(?![a-z0-9])'
    else:
        pattern = rf'(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])'
    return re.search(pattern, text) is not None


def _matches(mapping: dict[str, tuple[str, ...]], text: str) -> list[str]:
    return [key for key, values in mapping.items() if any(_contains_term(text, value) for value in values)]


def _term_matches(values: Iterable[str], text: str) -> list[str]:
    return [value for value in values if _contains_term(text, value)]


def _domain_decision(
    *,
    text: str,
    scope: str,
    categories: list[str],
    species: list[str],
    urgent: bool,
) -> tuple[bool, str, list[str], list[str]]:
    positive = list(dict.fromkeys(_term_matches(VETERINARY_TERMS, text)))
    clinical_intent = list(dict.fromkeys(_term_matches(CLINICAL_INTENT_TERMS, text)))
    pet_operation = list(dict.fromkeys(_term_matches(PET_OPERATION_TERMS, text)))
    negative: list[str] = []
    for domain, values in OUT_OF_DOMAIN_TERMS.items():
        if any(_contains_term(text, value) for value in values):
            negative.append(domain)

    strong_evidence = bool(positive or species or urgent)
    category_evidence = any(category != 'clinical_history' for category in categories)

    if negative and not strong_evidence and not category_evidence:
        return (
            False,
            'La consulta contiene indicadores claros de un dominio no veterinario.',
            positive + clinical_intent,
            negative,
        )

    if scope in {'clinical', 'pet'}:
        if strong_evidence or category_evidence or clinical_intent or (scope == 'pet' and pet_operation):
            return (
                True,
                'La consulta contiene vocabulario veterinario o una intencion clinica reconocible.',
                positive + clinical_intent + pet_operation,
                negative,
            )
        return (
            False,
            'No se detectaron sintomas, especies, pacientes ni conceptos clinicos suficientes.',
            positive + clinical_intent + pet_operation,
            negative,
        )

    if strong_evidence or category_evidence:
        return (
            True,
            'La consulta contiene vocabulario veterinario, preventivo o de cuidado animal.',
            positive + clinical_intent + pet_operation,
            negative,
        )

    return (
        False,
        'No se detecto evidencia suficiente de que la consulta pertenezca al ambito veterinario.',
        positive + clinical_intent + pet_operation,
        negative,
    )


def analyse_query(question: str, *, scope: str = 'mixed') -> QueryProfile:
    """Classify a question without asking an LLM to make routing decisions."""
    text = normalise(question)
    categories = _matches(CATEGORY_KEYWORDS, text)
    species = _matches(SPECIES_KEYWORDS, text)
    countries = _matches(COUNTRY_KEYWORDS, text)
    urgency_matches = [item for item in URGENCY_KEYWORDS if _contains_term(text, item)]
    keywords = [
        token for token in text.split()
        if len(token) >= 4 and token not in STOPWORDS
    ]
    keywords = list(dict.fromkeys(keywords))[:20]
    in_domain, reason, positive, negative = _domain_decision(
        text=text,
        scope=scope,
        categories=categories,
        species=species,
        urgent=bool(urgency_matches),
    )
    return QueryProfile(
        normalised_question=text,
        categories=categories,
        species=species,
        countries=countries,
        keywords=keywords,
        urgent=bool(urgency_matches),
        urgency_matches=urgency_matches,
        scope=scope,
        in_domain=in_domain,
        domain_reason=reason,
        domain_positive_matches=positive,
        domain_negative_matches=negative,
    )


def lexical_overlap(keywords: Iterable[str], text: str) -> float:
    """Return the fraction of relevant query terms found in a candidate chunk."""
    unique = list(dict.fromkeys(keywords))
    if not unique:
        return 0.0
    candidate = normalise(text)
    hits = sum(1 for keyword in unique if keyword in candidate)
    return hits / len(unique)


def rerank_score(
    *,
    dense_score: float,
    profile: QueryProfile,
    text: str,
    category: str | None,
    species: str | None,
    country: str | None,
    trust_level: str | None,
) -> float:
    """Combine semantic similarity with transparent metadata bonuses."""
    score = dense_score * 0.78
    score += lexical_overlap(profile.keywords, text) * 0.12
    if category and category in profile.categories:
        score += 0.05
    if species and species in profile.species:
        score += 0.025
    if country and country in profile.countries:
        score += 0.025
    if trust_level == 'official':
        score += 0.02
    return max(0.0, min(round(score, 6), 1.0))
