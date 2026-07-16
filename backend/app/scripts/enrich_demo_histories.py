"""Add recurrent, fully fictitious events used to demonstrate clinical RAG.

The script is idempotent and can be run against databases created by earlier
versions. It never changes owner data or real records.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import re

from sqlalchemy import select

from app.database import SessionLocal
from app.models import ClinicalEvent, Pet


DEMO_CASES: dict[str, list[dict[str, str]]] = {
    'Luna': [
        {'code': 'joint-1', 'type': 'consultation', 'title': 'Rigidez al levantarse', 'description': 'El propietario refiere rigidez tras periodos de reposo y menor disposicion para subir escaleras.', 'diagnosis': 'Molestia osteoarticular en seguimiento', 'treatment': 'Control de peso y revision de movilidad.'},
        {'code': 'joint-2', 'type': 'checkup', 'title': 'Seguimiento de movilidad', 'description': 'Persisten molestias articulares leves despues de ejercicio prolongado, sin signos de urgencia.', 'diagnosis': 'Seguimiento locomotor preventivo', 'treatment': 'Mantener ejercicio moderado y nueva valoracion.'},
    ],
    'Rocky': [
        {'code': 'joint-1', 'type': 'consultation', 'title': 'Rigidez de cadera', 'description': 'Episodio recurrente de rigidez de cadera al inicio del paseo.', 'diagnosis': 'Alteracion locomotora cronica en seguimiento', 'treatment': 'Control de movilidad y peso.'},
        {'code': 'joint-2', 'type': 'checkup', 'title': 'Revision osteoarticular', 'description': 'Se revisa la evolucion de la rigidez y la tolerancia al ejercicio.', 'diagnosis': 'Seguimiento de cadera', 'treatment': 'Continuar controles periodicos.'},
    ],
    'Salem': [
        {'code': 'joint-1', 'type': 'consultation', 'title': 'Rigidez articular ocasional', 'description': 'Menor actividad y rigidez leve al saltar despues de descansar.', 'diagnosis': 'Molestia articular felina en seguimiento', 'treatment': 'Vigilancia de movilidad y condicion corporal.'},
        {'code': 'joint-2', 'type': 'checkup', 'title': 'Control de movilidad felina', 'description': 'Se mantiene la rigidez ocasional sin empeoramiento registrado.', 'diagnosis': 'Seguimiento locomotor preventivo', 'treatment': 'Nueva revision si aumenta la limitacion.'},
    ],
    'Max': [
        {'code': 'skin-1', 'type': 'consultation', 'title': 'Brote de dermatitis estacional', 'description': 'Prurito y enrojecimiento recurrente coincidiendo con cambio de estacion.', 'diagnosis': 'Dermatitis ambiental recurrente', 'treatment': 'Control dermatologico y revision si progresa.'},
        {'code': 'skin-2', 'type': 'consultation', 'title': 'Revision dermatologica', 'description': 'Nuevo episodio leve de prurito en extremidades y abdomen.', 'diagnosis': 'Reaparicion de dermatitis', 'treatment': 'Seguimiento clinico.'},
        {'code': 'resp-1', 'type': 'consultation', 'title': 'Dificultad respiratoria con calor', 'description': 'Respiracion ruidosa y menor tolerancia al paseo en horas calurosas.', 'diagnosis': 'Episodio respiratorio asociado a calor', 'treatment': 'Evitar ejercicio intenso y valorar si reaparece.'},
    ],
    'Bruno': [
        {'code': 'resp-1', 'type': 'consultation', 'title': 'Intolerancia al ejercicio', 'description': 'Fatiga y respiracion ruidosa durante paseo con temperatura elevada.', 'diagnosis': 'Episodio respiratorio recurrente', 'treatment': 'Control ambiental y seguimiento.'},
        {'code': 'resp-2', 'type': 'checkup', 'title': 'Revision respiratoria', 'description': 'Se revisa la tolerancia al ejercicio y la recuperacion tras actividad.', 'diagnosis': 'Seguimiento respiratorio preventivo', 'treatment': 'Vigilancia de signos de alarma.'},
    ],
    'Simba': [
        {'code': 'resp-1', 'type': 'consultation', 'title': 'Jadeo prolongado tras ejercicio', 'description': 'Recuperacion mas lenta de lo habitual despues de actividad moderada.', 'diagnosis': 'Intolerancia al ejercicio en estudio', 'treatment': 'Reducir intensidad y revisar evolucion.'},
        {'code': 'resp-2', 'type': 'checkup', 'title': 'Control de tolerancia respiratoria', 'description': 'Se comprueba evolucion del jadeo y respuesta al ejercicio.', 'diagnosis': 'Seguimiento respiratorio', 'treatment': 'Mantener observacion.'},
    ],
    'Kira': [
        {'code': 'ear-1', 'type': 'consultation', 'title': 'Otitis externa', 'description': 'Enrojecimiento y sacudidas de cabeza compatibles con nuevo episodio de otitis.', 'diagnosis': 'Otitis externa recurrente', 'treatment': 'Limpieza y control veterinario.'},
        {'code': 'ear-2', 'type': 'consultation', 'title': 'Reaparicion de molestias auriculares', 'description': 'Prurito auricular y cerumen tras varios meses sin sintomas.', 'diagnosis': 'Recidiva de otitis', 'treatment': 'Seguimiento del conducto auditivo.'},
        {'code': 'ear-3', 'type': 'checkup', 'title': 'Control de oidos', 'description': 'Revision preventiva por antecedentes de otitis recurrente.', 'diagnosis': 'Seguimiento auricular', 'treatment': 'Mantener higiene pautada.'},
    ],
    'Mia': [
        {'code': 'renal-1', 'type': 'laboratory', 'title': 'Control de funcion renal', 'description': 'Analitica de seguimiento por antecedente renal cronico inicial.', 'diagnosis': 'Enfermedad renal cronica en seguimiento', 'treatment': 'Controles periodicos y vigilancia de hidratacion.'},
        {'code': 'renal-2', 'type': 'consultation', 'title': 'Revision renal', 'description': 'Se revisan apetito, ingesta de agua, peso y evolucion general.', 'diagnosis': 'Seguimiento renal estable', 'treatment': 'Mantener controles programados.'},
        {'code': 'renal-3', 'type': 'laboratory', 'title': 'Nueva analitica renal', 'description': 'Control repetido de parametros renales dentro del seguimiento preventivo.', 'diagnosis': 'Control de enfermedad renal', 'treatment': 'Continuar vigilancia veterinaria.'},
    ],
    'Cleo': [
        {'code': 'weight-1', 'type': 'nutrition', 'title': 'Perdida de peso', 'description': 'Descenso leve de peso detectado en control rutinario.', 'diagnosis': 'Perdida de peso en estudio', 'treatment': 'Seguimiento de peso y apetito.'},
        {'code': 'weight-2', 'type': 'checkup', 'title': 'Control de peso senior', 'description': 'Se repite control por tendencia descendente de peso.', 'diagnosis': 'Seguimiento nutricional', 'treatment': 'Valorar pruebas si continua el descenso.'},
    ],
    'Nina': [
        {'code': 'digestive-1', 'type': 'consultation', 'title': 'Episodio digestivo recurrente', 'description': 'Vomito ocasional y sensibilidad digestiva sin signos de urgencia.', 'diagnosis': 'Sensibilidad digestiva en seguimiento', 'treatment': 'Vigilar tolerancia alimentaria.'},
        {'code': 'digestive-2', 'type': 'nutrition', 'title': 'Revision de tolerancia alimentaria', 'description': 'Se revisa dieta por nuevos signos digestivos leves.', 'diagnosis': 'Seguimiento digestivo', 'treatment': 'Mantener control veterinario.'},
    ],
}


def _slug(value: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', value.casefold()).strip('-')


def run() -> None:
    """Insert missing demonstration events and report the number created."""
    db = SessionLocal()
    created = 0
    try:
        now = datetime.now(timezone.utc)
        for pet_name, cases in DEMO_CASES.items():
            pet = db.scalar(select(Pet).where(Pet.name == pet_name))
            if pet is None:
                continue
            for index, case in enumerate(cases, start=1):
                external_id = f'RAG-DEMO-{_slug(pet_name)}-{case["code"]}'
                exists = db.scalar(select(ClinicalEvent.id).where(ClinicalEvent.external_id == external_id))
                if exists:
                    continue
                event_date = now - timedelta(days=60 + index * 115 + len(pet_name) * 3)
                db.add(
                    ClinicalEvent(
                        pet_id=pet.id,
                        external_id=external_id,
                        event_date=event_date,
                        event_type=case['type'],
                        title=case['title'],
                        description=case['description'],
                        diagnosis=case['diagnosis'],
                        treatment=case['treatment'],
                        weight_kg=Decimal(pet.weight_kg),
                        visible_to_owner=True,
                    )
                )
                created += 1
        db.commit()
        print(f'Eventos clinicos ficticios anadidos: {created}')
    finally:
        db.close()


if __name__ == '__main__':
    run()
