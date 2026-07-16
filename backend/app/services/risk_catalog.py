"""Versioned catalogue of preventive rules used by GamuCare AI.

The rules are deliberately conservative. They do not diagnose a disease; they
surface review candidates from structured data, overdue plan services and
repeated terms in fictitious clinical records. Every externally informed rule
keeps a source URL so the clinic can audit the rationale.
"""
from __future__ import annotations

from datetime import date
from typing import Any

RuleDefinition = dict[str, Any]

WSAVA_VACCINATION_ES = (
    'https://wsava.org/wp-content/uploads/2024/05/'
    'ESP.-J-of-Small-Animal-Practice-2024-Squires-2024-guidelines-for-the-vaccination-of-dogs-and-cats-compiled-by-the.pdf'
)
AAHA_SENIOR = 'https://www.aaha.org/resources/2023-aaha-senior-care-guidelines-for-dogs-and-cats/'
WSAVA_NUTRITION = 'https://wsava.org/Global-Guidelines/Global-Nutrition-Guidelines/'
ESCCAP_GUIDELINES = 'https://www.esccap.org/guidelines/'
CAMBRIDGE_BOAS = 'https://www.vet.cam.ac.uk/boas/about-boas'
IRIS_GUIDELINES = 'https://www.iris-kidney.com/iris-guidelines-1'

RISK_RULE_CATALOG: list[RuleDefinition] = [
    {
        'code': 'DOG_SENIOR',
        'name': 'Revisión preventiva de perro senior',
        'description': 'Marca perros de ocho años o más para revisar si el seguimiento preventivo debe adaptarse a su etapa vital.',
        'category': 'life_stage',
        'species': 'dog',
        'conditions': {'species': 'dog', 'min_age_years': 8},
        'severity': 'medium',
        'source': 'AAHA Senior Care Guidelines 2023',
        'source_url': AAHA_SENIOR,
        'source_date': date(2023, 1, 1),
        'auto_resolve': True,
        'version': 2,
    },
    {
        'code': 'CAT_SENIOR',
        'name': 'Revisión preventiva de gato senior',
        'description': 'Marca gatos de diez años o más para revisar el plan preventivo y la frecuencia de controles.',
        'category': 'life_stage',
        'species': 'cat',
        'conditions': {'species': 'cat', 'min_age_years': 10},
        'severity': 'medium',
        'source': 'AAHA Senior Care Guidelines 2023',
        'source_url': AAHA_SENIOR,
        'source_date': date(2023, 1, 1),
        'auto_resolve': True,
        'version': 2,
    },
    {
        'code': 'BRACHY_RESP',
        'name': 'Vigilancia respiratoria en raza braquicéfala',
        'description': 'Propone revisar signos respiratorios o intolerancia al ejercicio en razas braquicéfalas registradas.',
        'category': 'respiratory',
        'species': 'dog',
        'conditions': {
            'species': 'dog',
            'breeds': ['Bulldog Frances', 'Bulldog Francés', 'Carlino', 'Pug', 'Boxer', 'Bulldog Ingles', 'Bulldog Inglés'],
        },
        'severity': 'medium',
        'source': 'University of Cambridge BOAS Research Group',
        'source_url': CAMBRIDGE_BOAS,
        'source_date': None,
        'auto_resolve': False,
        'version': 2,
    },
    {
        'code': 'RENAL_HISTORY',
        'name': 'Antecedentes renales registrados',
        'description': 'Detecta referencias renales previas para facilitar su seguimiento por el veterinario.',
        'category': 'renal',
        'species': None,
        'conditions': {
            'history_contains': ['renal', 'riñon', 'riñón', 'creatinina', 'sdma'],
            'history_min_occurrences': 1,
        },
        'severity': 'high',
        'source': 'International Renal Interest Society (IRIS)',
        'source_url': IRIS_GUIDELINES,
        'source_date': None,
        'auto_resolve': False,
        'version': 2,
    },
    {
        'code': 'JOINT_HISTORY',
        'name': 'Antecedentes osteoarticulares registrados',
        'description': 'Agrupa referencias a dolor, rigidez o problemas articulares para revisar su evolución.',
        'category': 'musculoskeletal',
        'species': None,
        'conditions': {
            'history_contains': ['articular', 'artrosis', 'cadera', 'cojera', 'rigidez'],
            'history_min_occurrences': 1,
        },
        'severity': 'medium',
        'source': 'Regla clínica interna sobre antecedentes documentados',
        'source_url': None,
        'source_date': None,
        'auto_resolve': False,
        'version': 2,
    },
    {
        'code': 'RECURRENT_OTITIS',
        'name': 'Episodios de otitis recurrentes',
        'description': 'Detecta dos o más menciones relacionadas con otitis en los últimos veinticuatro meses.',
        'category': 'dermatology',
        'species': None,
        'conditions': {
            'history_contains': ['otitis', 'oído', 'oido', 'auricular'],
            'history_min_occurrences': 2,
            'history_lookback_months': 24,
        },
        'severity': 'medium',
        'source': 'Regla clínica interna basada en recurrencia documental',
        'source_url': None,
        'source_date': None,
        'auto_resolve': True,
        'version': 1,
    },
    {
        'code': 'RECURRENT_DIGESTIVE',
        'name': 'Episodios digestivos recurrentes',
        'description': 'Detecta dos o más episodios digestivos documentados en los últimos doce meses.',
        'category': 'digestive',
        'species': None,
        'conditions': {
            'history_contains': ['diarrea', 'vómito', 'vomito', 'gastroenteritis', 'digestivo'],
            'history_min_occurrences': 2,
            'history_lookback_months': 12,
        },
        'severity': 'medium',
        'source': 'Regla clínica interna basada en recurrencia documental',
        'source_url': None,
        'source_date': None,
        'auto_resolve': True,
        'version': 1,
    },
    {
        'code': 'RECURRENT_DERMATOLOGY',
        'name': 'Problemas dermatológicos recurrentes',
        'description': 'Detecta dos o más episodios de dermatitis, prurito o alergia en los últimos dieciocho meses.',
        'category': 'dermatology',
        'species': None,
        'conditions': {
            'history_contains': ['dermatitis', 'prurito', 'alergia', 'alérgico', 'alergico'],
            'history_min_occurrences': 2,
            'history_lookback_months': 18,
        },
        'severity': 'medium',
        'source': 'Regla clínica interna basada en recurrencia documental',
        'source_url': None,
        'source_date': None,
        'auto_resolve': True,
        'version': 1,
    },
    {
        'code': 'WEIGHT_LOSS_TREND',
        'name': 'Pérdida de peso relevante en seguimiento',
        'description': 'Compara pesos clínicos recientes y marca descensos iguales o superiores al 10 % dentro de seis meses.',
        'category': 'nutrition',
        'species': None,
        'conditions': {
            'weight_change_pct_lte': -10,
            'weight_lookback_months': 6,
            'minimum_weight_records': 2,
        },
        'severity': 'high',
        'source': 'WSAVA Global Nutrition Guidelines and Toolkit',
        'source_url': WSAVA_NUTRITION,
        'source_date': None,
        'auto_resolve': True,
        'version': 1,
    },
    {
        'code': 'WEIGHT_GAIN_TREND',
        'name': 'Aumento de peso relevante en seguimiento',
        'description': 'Compara pesos clínicos recientes y marca aumentos iguales o superiores al 10 % dentro de seis meses.',
        'category': 'nutrition',
        'species': None,
        'conditions': {
            'weight_change_pct_gte': 10,
            'weight_lookback_months': 6,
            'minimum_weight_records': 2,
        },
        'severity': 'medium',
        'source': 'WSAVA Global Nutrition Guidelines and Toolkit',
        'source_url': WSAVA_NUTRITION,
        'source_date': None,
        'auto_resolve': True,
        'version': 1,
    },
    {
        'code': 'VACCINATION_OVERDUE',
        'name': 'Vacunación incluida vencida',
        'description': 'Detecta prestaciones de vacunación vencidas dentro del plan activo.',
        'category': 'vaccination',
        'species': None,
        'conditions': {'overdue_service_types': ['vaccination'], 'overdue_days_min': 1},
        'severity': 'high',
        'source': 'WSAVA Vaccination Guidelines 2024',
        'source_url': WSAVA_VACCINATION_ES,
        'source_date': date(2024, 1, 1),
        'auto_resolve': True,
        'version': 1,
    },
    {
        'code': 'PARASITE_CONTROL_OVERDUE',
        'name': 'Control antiparasitario incluido vencido',
        'description': 'Detecta prestaciones antiparasitarias vencidas dentro del plan activo.',
        'category': 'parasites',
        'species': None,
        'conditions': {'overdue_service_types': ['deworming'], 'overdue_days_min': 1},
        'severity': 'medium',
        'source': 'ESCCAP Guidelines',
        'source_url': ESCCAP_GUIDELINES,
        'source_date': None,
        'auto_resolve': True,
        'version': 1,
    },
    {
        'code': 'PREVENTIVE_CHECKUP_OVERDUE',
        'name': 'Revisión preventiva incluida vencida',
        'description': 'Detecta revisiones preventivas del plan que llevan al menos treinta días vencidas.',
        'category': 'preventive_care',
        'species': None,
        'conditions': {'overdue_service_types': ['checkup', 'laboratory'], 'overdue_days_min': 30},
        'severity': 'medium',
        'source': 'Regla operativa interna del plan LifeCare',
        'source_url': None,
        'source_date': None,
        'auto_resolve': True,
        'version': 1,
    },
]


def by_code() -> dict[str, RuleDefinition]:
    """Return a defensive mapping for seed and upgrade scripts."""
    return {str(rule['code']): dict(rule) for rule in RISK_RULE_CATALOG}
