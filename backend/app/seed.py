"""Create deterministic demonstration data for the MVP.

The data set contains no real personal or clinical information. Re-running the
module is safe because it stops when the initial clinic account already exists.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
import logging

from sqlalchemy import select

from app.core.security import hash_password
from app.database import SessionLocal
from app.models import (
    ClinicalEvent,
    HealthPlan,
    ImportBatch,
    Owner,
    Pet,
    PetPlanSubscription,
    PlanService,
    RiskRule,
    SubscriptionService,
    User,
)
from app.services.risk_catalog import RISK_RULE_CATALOG
from app.services.risk_engine import rebuild_alerts
from app.services.subscriptions import generate_installments

logger = logging.getLogger(__name__)
DEMO_PASSWORD = 'GamuCare123!'


def add_months(value: date, months: int) -> date:
    """Add whole months while keeping the day valid for the target month."""
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    month_days = [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
                  31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    return date(year, month, min(value.day, month_days[month - 1]))


def birth_date_for_age(age: int, month_offset: int) -> date:
    today = date.today()
    return add_months(date(today.year - age, today.month, min(today.day, 20)), -month_offset)


def service(name: str, service_type: str, mode: str = 'limited', quantity: int | None = 1,
            frequency: int | None = None, notes: str | None = None) -> dict:
    return {
        'name': name,
        'service_type': service_type,
        'service_mode': mode,
        'included_quantity': quantity,
        'frequency_months': frequency,
        'notes': notes,
    }


COMMON_DISCOUNTS = [
    service('10 % en cirugia de tejidos blandos y limpieza bucal', 'discount', 'discount', None),
    service('10 % en pruebas diagnosticas', 'discount', 'discount', None, notes='No incluye pruebas de especialistas.'),
    service('10 % en laboratorio interno', 'discount', 'discount', None, notes='Laboratorio externo no incluido.'),
    service('5 % en juguetes y accesorios', 'discount', 'discount', None),
]

PLAN_DEFINITIONS = [
    {
        'name': 'LifeCare Baby Perros', 'species': 'dog', 'lifecycle': 'baby',
        'description': 'Plan para cachorros durante sus primeros meses de vida.',
        'monthly': '50.00', 'single': '595.00',
        'services': [
            service('Consultas veterinarias ilimitadas', 'consultation', 'unlimited', None),
            service('Revisiones generales ilimitadas', 'checkup', 'unlimited', None),
            service('Primera vacuna heptavalente', 'vaccination'),
            service('Segunda vacuna heptavalente', 'vaccination'),
            service('Vacuna de la rabia', 'vaccination'),
            service('Vacuna KC (gripe canina)', 'vaccination'),
            service('Test de Leishmania', 'diagnostic_test', notes='La vacuna de Leishmania no esta incluida.'),
            service('Coprologico y test de Giardia', 'diagnostic_test'),
            service('Desparasitacion interna trimestral', 'deworming', 'periodic', 4, 3, 'No incluye extras.'),
            service('Desparasitacion externa', 'deworming', 'limited', 5, None, 'Incluye cinco pipetas.'),
            service('Collar antiparasitario', 'deworming'),
            service('Microchip y alta RAIA', 'administrative'),
            service('Analitica pre-esterilizacion', 'laboratory', notes='Hemograma, bioquimica basica e iones.'),
            service('Electrocardiograma', 'diagnostic_test'),
            service('Revision de muda dentaria y salud bucal', 'dental'),
            service('Asesoramiento personalizado sobre nutricion y cuidados', 'nutrition'),
            service('Atencion telefonica 24 h', 'support', 'benefit', None),
            service('Kit LifeCare Baby de bienvenida', 'benefit', 'benefit', None),
        ] + COMMON_DISCOUNTS,
    },
    {
        'name': 'LifeCare Active Perros', 'species': 'dog', 'lifecycle': 'active',
        'description': 'Plan anual para perros adultos jovenes y sanos, de uno a ocho anos.',
        'monthly': '45.00', 'single': '495.00',
        'services': [
            service('Consultas veterinarias ilimitadas', 'consultation', 'unlimited', None),
            service('Revisiones generales ilimitadas', 'checkup', 'unlimited', None),
            service('Consultas preventivas trimestrales', 'checkup', 'periodic', 4, 3),
            service('Vacuna heptavalente', 'vaccination'),
            service('Vacuna de la rabia', 'vaccination'),
            service('Vacuna KC (gripe canina)', 'vaccination'),
            service('Test de Leishmania', 'diagnostic_test', notes='La vacuna de Leishmania no esta incluida.'),
            service('Desparasitacion interna trimestral', 'deworming', 'periodic', 4, 3, 'No incluye extras.'),
            service('Desparasitacion externa', 'deworming', 'limited', 5, None, 'Incluye cinco pipetas.'),
            service('Collar antiparasitario', 'deworming'),
            service('Analitica anual completa', 'laboratory', notes='Hemograma, bioquimica, iones y SDMA.'),
            service('Electrocardiograma', 'diagnostic_test'),
            service('Revision bucodental', 'dental'),
            service('Asesoramiento nutricional', 'nutrition'),
            service('Atencion telefonica 24 h', 'support', 'benefit', None),
            service('Kit LifeCare Active de bienvenida', 'benefit', 'benefit', None),
        ] + COMMON_DISCOUNTS,
    },
    {
        'name': 'LifeCare Total Perros', 'species': 'dog', 'lifecycle': 'total',
        'description': 'Plan para perros mayores de ocho anos o pacientes con seguimiento especial.',
        'monthly': '60.00', 'single': '695.00',
        'services': [
            service('Consultas veterinarias ilimitadas', 'consultation', 'unlimited', None),
            service('Revisiones generales ilimitadas', 'checkup', 'unlimited', None),
            service('Consultas preventivas trimestrales', 'checkup', 'periodic', 4, 3),
            service('Vacuna heptavalente', 'vaccination'),
            service('Vacuna de la rabia', 'vaccination'),
            service('Vacuna KC (gripe canina)', 'vaccination'),
            service('Control de Leishmania', 'diagnostic_test', notes='La vacuna de Leishmania no esta incluida.'),
            service('Desparasitacion interna trimestral', 'deworming', 'periodic', 4, 3, 'No incluye extras.'),
            service('Desparasitacion externa', 'deworming', 'limited', 5, None, 'Incluye cinco pipetas.'),
            service('Collar antiparasitario', 'deworming'),
            service('Analitica anual Plus', 'laboratory', notes='Hemograma, bioquimica, iones, SDMA y T4.'),
            service('Electrocardiograma', 'diagnostic_test'),
            service('Revision bucodental', 'dental'),
            service('Ecografia basica y radiografia de dos proyecciones', 'diagnostic_imaging'),
            service('Revision de tratamientos y seguimiento personalizado', 'treatment_review'),
            service('Asesoramiento nutricional adaptado a edad y condicion', 'nutrition'),
            service('Atencion telefonica 24 h', 'support', 'benefit', None),
            service('Kit LifeCare Total de bienvenida', 'benefit', 'benefit', None),
        ] + COMMON_DISCOUNTS,
    },
    {
        'name': 'LifeCare Baby Gatos', 'species': 'cat', 'lifecycle': 'baby',
        'description': 'Plan para gatitos durante sus primeros meses de vida.',
        'monthly': '35.00', 'single': '395.00',
        'services': [
            service('Consultas veterinarias ilimitadas', 'consultation', 'unlimited', None),
            service('Revisiones generales ilimitadas', 'checkup', 'unlimited', None),
            service('Consultas preventivas trimestrales', 'checkup', 'periodic', 4, 3),
            service('Vacuna trivalente', 'vaccination'),
            service('Vacuna de leucemia felina', 'vaccination'),
            service('Vacuna tetravalente', 'vaccination'),
            service('Test triple felino', 'diagnostic_test'),
            service('Coprologico y test de Giardia', 'diagnostic_test'),
            service('Desparasitacion interna y externa semestral', 'deworming', 'periodic', 2, 6),
            service('Microchip y alta RAIA', 'administrative'),
            service('Analitica pre-esterilizacion', 'laboratory', notes='Hemograma, bioquimica basica e iones.'),
            service('Revision de muda dentaria y salud bucal', 'dental'),
            service('Asesoramiento personalizado sobre nutricion y cuidados', 'nutrition'),
            service('Atencion telefonica 24 h', 'support', 'benefit', None),
            service('Kit LifeCare Baby de bienvenida', 'benefit', 'benefit', None),
        ] + COMMON_DISCOUNTS,
    },
    {
        'name': 'LifeCare Active Gatos', 'species': 'cat', 'lifecycle': 'active',
        'description': 'Plan anual para gatos adultos jovenes y sanos, de uno a ocho anos.',
        'monthly': '30.00', 'single': '359.00',
        'services': [
            service('Consultas veterinarias ilimitadas', 'consultation', 'unlimited', None),
            service('Revisiones generales ilimitadas', 'checkup', 'unlimited', None),
            service('Consultas preventivas trimestrales', 'checkup', 'periodic', 4, 3),
            service('Vacuna tetravalente o trivalente', 'vaccination'),
            service('Desparasitacion interna y externa semestral', 'deworming', 'periodic', 2, 6),
            service('Analitica anual completa', 'laboratory', notes='Hemograma, bioquimica, iones y SDMA.'),
            service('Electrocardiograma', 'diagnostic_test'),
            service('Limpieza dental y revision bucodental', 'dental', notes='No incluye extracciones.'),
            service('Asesoramiento nutricional', 'nutrition'),
            service('Atencion telefonica 24 h', 'support', 'benefit', None),
            service('Kit LifeCare Active de bienvenida', 'benefit', 'benefit', None),
        ] + COMMON_DISCOUNTS,
    },
    {
        'name': 'LifeCare Total Gatos', 'species': 'cat', 'lifecycle': 'total',
        'description': 'Plan para gatos mayores de ocho anos o pacientes con seguimiento especial.',
        'monthly': '45.00', 'single': '495.00',
        'services': [
            service('Consultas veterinarias ilimitadas', 'consultation', 'unlimited', None),
            service('Revisiones generales ilimitadas', 'checkup', 'unlimited', None),
            service('Consultas preventivas trimestrales', 'checkup', 'periodic', 4, 3),
            service('Vacuna tetravalente o trivalente', 'vaccination'),
            service('Desparasitacion interna y externa semestral', 'deworming', 'periodic', 2, 6),
            service('Analitica anual Plus', 'laboratory', notes='Hemograma, bioquimica, iones, SDMA y T4.'),
            service('Electrocardiograma', 'diagnostic_test'),
            service('Ecografia basica y radiografia de dos proyecciones', 'diagnostic_imaging'),
            service('Limpieza y revision bucodental', 'dental', notes='No incluye extracciones dentales.'),
            service('Revision de tratamientos y seguimiento personalizado', 'treatment_review'),
            service('Asesoramiento nutricional adaptado a edad y condicion', 'nutrition'),
            service('Atencion telefonica 24 h', 'support', 'benefit', None),
            service('Kit LifeCare Total de bienvenida', 'benefit', 'benefit', None),
        ] + COMMON_DISCOUNTS,
    },
]

OWNERS = [
    ('Elena', 'Martin Ruiz', '600100001', 'Calle Alcala 101, Madrid'),
    ('David', 'Santos Mora', '600100002', 'Avenida de America 12, Madrid'),
    ('Laura', 'Gil Navarro', '600100003', 'Calle Toledo 88, Madrid'),
    ('Javier', 'Ortega Leon', '600100004', 'Calle Segovia 30, Madrid'),
    ('Marta', 'Ramos Nieto', '600100005', 'Calle Atocha 155, Madrid'),
    ('Sergio', 'Vega Pastor', '600100006', 'Paseo de Extremadura 44, Madrid'),
    ('Ana', 'Prieto Molina', '600100007', 'Calle Ibiza 22, Madrid'),
    ('Pablo', 'Herrera Cano', '600100008', 'Calle Embajadores 73, Madrid'),
    ('Lucia', 'Dominguez Rey', '600100009', 'Calle Princesa 56, Madrid'),
    ('Alberto', 'Nunez Vidal', '600100010', 'Calle Bravo Murillo 181, Madrid'),
    ('Irene', 'Lopez Serra', '600100011', 'Calle Arturo Soria 95, Madrid'),
    ('Ruben', 'Calvo Duran', '600100012', 'Calle Cartagena 40, Madrid'),
    ('Sara', 'Mendez Soler', '600100013', 'Calle Delicias 64, Madrid'),
    ('Hector', 'Blanco Costa', '600100014', 'Calle Oca 19, Madrid'),
    ('Noelia', 'Castro Pena', '600100015', 'Calle Silvano 77, Madrid'),
]

PETS = [
    ('Luna', 'dog', 'Labrador Retriever', 9, 'female', '38.0', True, None, 'Sobrepeso y molestias articulares intermitentes.'),
    ('Max', 'dog', 'Bulldog Frances', 6, 'male', '14.2', True, 'Dermatitis ambiental estacional.', 'Episodios respiratorios con calor.'),
    ('Nala', 'dog', 'Beagle', 4, 'female', '15.0', True, None, None),
    ('Rocky', 'dog', 'Pastor Aleman', 10, 'male', '39.0', True, None, 'Rigidez de cadera en seguimiento.'),
    ('Coco', 'dog', 'Chihuahua', 2, 'male', '3.1', False, None, None),
    ('Kira', 'dog', 'Golden Retriever', 8, 'female', '34.0', True, None, 'Otitis recurrente leve.'),
    ('Thor', 'dog', 'Mastin Espanol', 7, 'male', '55.0', True, None, None),
    ('Lola', 'dog', 'Caniche', 12, 'female', '7.0', True, None, 'Soplo cardiaco leve controlado.'),
    ('Simba', 'dog', 'Boxer', 5, 'male', '31.0', True, None, None),
    ('Toby', 'dog', 'Border Collie', 3, 'male', '20.0', False, None, None),
    ('Bruno', 'dog', 'Carlino', 9, 'male', '11.0', True, None, 'Intolerancia al ejercicio en verano.'),
    ('Maya', 'dog', 'Mestizo', 0, 'female', '6.3', False, None, None),
    ('Miso', 'cat', 'British Shorthair', 2, 'male', '5.2', True, None, None),
    ('Cleo', 'cat', 'Siames', 11, 'female', '4.1', True, None, 'Perdida de peso leve en estudio.'),
    ('Milo', 'cat', 'Maine Coon', 8, 'male', '8.1', True, None, None),
    ('Sombra', 'cat', 'Comun Europeo', 4, 'female', '4.8', True, None, None),
    ('Nina', 'cat', 'Persa', 10, 'female', '5.9', True, 'Sensibilidad digestiva.', 'Lagrimeo cronico leve.'),
    ('Leo', 'cat', 'Bengali', 3, 'male', '6.0', True, None, None),
    ('Gala', 'cat', 'Ragdoll', 6, 'female', '6.8', True, None, None),
    ('Felix', 'cat', 'Sphynx', 1, 'male', '4.0', False, None, None),
    ('Mia', 'cat', 'Comun Europeo', 14, 'female', '4.3', True, None, 'Enfermedad renal cronica estadio inicial.'),
    ('Salem', 'cat', 'Scottish Fold', 7, 'male', '5.5', True, None, 'Rigidez articular ocasional.'),
    ('Tom', 'cat', 'Azul Ruso', 5, 'male', '5.0', True, None, None),
    ('Olivia', 'cat', 'Comun Europeo', 0, 'female', '2.1', False, None, None),
    ('Duna', 'dog', 'Galgo Espanol', 6, 'female', '24.0', True, None, None),
]

RISK_RULES = RISK_RULE_CATALOG



def create_plan_services(plan: HealthPlan, definitions: list[dict]) -> None:
    for order, item in enumerate(definitions, start=1):
        plan.services.append(
            PlanService(
                name=item['name'],
                description=None,
                service_type=item['service_type'],
                service_mode=item['service_mode'],
                included_quantity=item['included_quantity'],
                frequency_months=item['frequency_months'],
                mandatory=item['service_type'] in ('vaccination', 'laboratory'),
                display_order=order,
                notes=item['notes'],
            )
        )


def choose_lifecycle(age: int) -> str:
    if age < 1:
        return 'baby'
    if age <= 8:
        return 'active'
    return 'total'


def demo_payment_terms(plan: HealthPlan, pet_index: int, start: date, end: date) -> dict:
    """Return deterministic payment data for fictitious subscriptions.

    The sample deliberately combines one-off payments, six-instalment schedules
    and the maximum twelve-instalment schedule required by the MVP.
    """
    today = date.today()
    if pet_index % 3 == 0:
        return {
            'payment_mode': 'single',
            'installments_total': 1,
            'installments_paid': 1,
            'total_amount': plan.price_single,
        }

    installments_total = 12 if pet_index % 2 == 0 else 6
    months_elapsed = max(0, (today.year - start.year) * 12 + today.month - start.month)
    expected_paid = min(installments_total, (months_elapsed * installments_total) // 12 + 1)
    if pet_index % 5 == 1 and expected_paid > 0 and end >= today:
        expected_paid -= 1
    if end < today:
        expected_paid = installments_total
    return {
        'payment_mode': 'installments',
        'installments_total': installments_total,
        'installments_paid': expected_paid,
        'total_amount': plan.price_monthly * 12,
    }


def create_subscription_services(subscription: PetPlanSubscription, pet_index: int) -> None:
    today = date.today()
    for plan_service in subscription.health_plan.services:
        if plan_service.service_mode in ('unlimited', 'discount', 'benefit'):
            subscription.services.append(
                SubscriptionService(
                    plan_service=plan_service,
                    occurrence_number=1,
                    scheduled_date=None,
                    status='not_applicable',
                    notes='Prestacion disponible durante la vigencia del plan.' if plan_service.service_mode == 'unlimited' else plan_service.notes,
                )
            )
            continue

        quantity = plan_service.included_quantity or 1
        for occurrence in range(1, quantity + 1):
            if plan_service.frequency_months:
                scheduled = add_months(subscription.start_date, plan_service.frequency_months * occurrence - 1)
            else:
                scheduled = add_months(subscription.start_date, min(2 + occurrence * 2, 10))

            completion_selector = (pet_index + occurrence + plan_service.display_order) % 4
            completed = scheduled <= today and completion_selector not in (0,)
            if completed:
                status = 'completed'
                completed_date = scheduled + timedelta(days=(pet_index + occurrence) % 6)
            elif scheduled < today:
                status = 'overdue'
                completed_date = None
            elif scheduled <= today + timedelta(days=30):
                status = 'upcoming'
                completed_date = None
            else:
                status = 'pending'
                completed_date = None

            subscription.services.append(
                SubscriptionService(
                    plan_service=plan_service,
                    occurrence_number=occurrence,
                    scheduled_date=scheduled,
                    completed_date=completed_date,
                    status=status,
                )
            )


def create_history(pet: Pet, pet_index: int) -> None:
    event_templates = [
        ('checkup', 'Revision general', 'Exploracion general sin hallazgos de urgencia.'),
        ('vaccination', 'Revision de vacunacion', 'Se revisa la pauta preventiva y el estado general.'),
        ('deworming', 'Control antiparasitario', 'Se actualiza el calendario de desparasitacion.'),
        ('dental', 'Revision bucodental', 'Se valora higiene oral y presencia de sarro.'),
        ('nutrition', 'Control de peso y nutricion', 'Se revisa peso, condicion corporal y alimentacion.'),
        ('laboratory', 'Analitica de control', 'Resultados ficticios dentro del seguimiento preventivo.'),
        ('consultation', 'Consulta de seguimiento', 'Consulta programada con evolucion estable.'),
        ('diagnostic_test', 'Prueba diagnostica preventiva', 'Prueba incluida en el seguimiento del paciente.'),
    ]
    today = date.today()
    for position, (event_type, title, description) in enumerate(event_templates):
        days_back = 35 + position * 62 + pet_index * 3
        event_day = today - timedelta(days=days_back)
        pet.clinical_events.append(
            ClinicalEvent(
                external_id=f'WK-HIST-{pet_index + 1:03d}-{position + 1:02d}',
                event_date=datetime.combine(event_day, time(hour=10 + position % 6), tzinfo=timezone.utc),
                event_type=event_type,
                title=title,
                description=description,
                diagnosis=None,
                treatment=None,
                weight_kg=pet.weight_kg,
                visible_to_owner=position != 7,
            )
        )


def seed() -> None:
    db = SessionLocal()
    try:
        if db.scalar(select(User).where(User.email == 'clinic@gamucare.local')):
            logger.info('seed_skipped_existing_data')
            return

        staff = [
            User(email='clinic@gamucare.local', password_hash=hash_password(DEMO_PASSWORD), role='clinic', must_change_password=False),
            User(email='staff@gamucare.local', password_hash=hash_password(DEMO_PASSWORD), role='staff', must_change_password=False),
            User(email='technical@gamucare.local', password_hash=hash_password(DEMO_PASSWORD), role='technical', must_change_password=False),
        ]
        db.add_all(staff)

        plans: dict[tuple[str, str], HealthPlan] = {}
        for definition in PLAN_DEFINITIONS:
            plan = HealthPlan(
                name=definition['name'],
                species=definition['species'],
                lifecycle=definition['lifecycle'],
                description=definition['description'],
                duration_months=12,
                price_monthly=Decimal(definition['monthly']),
                price_single=Decimal(definition['single']),
            )
            create_plan_services(plan, definition['services'])
            db.add(plan)
            plans[(plan.species, plan.lifecycle)] = plan

        owners: list[Owner] = []
        for index, (first_name, last_name, phone, address) in enumerate(OWNERS, start=1):
            email = f'owner{index:02d}@example.test'
            user = User(email=email, password_hash=hash_password(DEMO_PASSWORD), role='owner', must_change_password=False)
            owner = Owner(
                user=user,
                external_id=f'WK-OWN-{index:04d}',
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                email=email,
                address=address,
            )
            db.add(owner)
            owners.append(owner)

        db.flush()
        today = date.today()
        for index, spec in enumerate(PETS):
            name, species, breed, age, sex, weight, neutered, allergies, chronic = spec
            pet = Pet(
                owner=owners[index % len(owners)],
                external_id=f'WK-PET-{index + 1:04d}',
                name=name,
                species=species,
                breed=breed,
                birth_date=birth_date_for_age(age, index % 10),
                sex=sex,
                weight_kg=Decimal(weight),
                neutered=neutered,
                microchip=f'72409810{index + 1:07d}',
                allergies=allergies,
                chronic_conditions=chronic,
            )
            create_history(pet, index)
            db.add(pet)
            db.flush()

            # Five patients intentionally remain without a plan to demonstrate the difference.
            if index not in (4, 9, 17, 22, 24):
                lifecycle = choose_lifecycle(age)
                plan = plans[(species, lifecycle)]
                if index % 7 == 0:
                    start = add_months(today, -14)
                elif index % 5 == 0:
                    start = add_months(today, -11)
                else:
                    start = add_months(today, -(index % 8 + 1))
                end = add_months(start, 12) - timedelta(days=1)
                if end < today:
                    plan_status = 'expired'
                elif end <= today + timedelta(days=45):
                    plan_status = 'expiring'
                else:
                    plan_status = 'active'
                subscription = PetPlanSubscription(
                    pet=pet,
                    health_plan=plan,
                    start_date=start,
                    end_date=end,
                    status=plan_status,
                    renewal_status='not_requested',
                    **demo_payment_terms(plan, index, start, end),
                )
                create_subscription_services(subscription, index)
                generate_installments(subscription, today=today)
                db.add(subscription)

        for definition in RISK_RULES:
            db.add(
                RiskRule(
                    code=definition['code'],
                    name=definition['name'],
                    description=definition.get('description'),
                    category=definition.get('category', 'general'),
                    species=definition.get('species'),
                    conditions=definition['conditions'],
                    severity=definition['severity'],
                    source=definition['source'],
                    source_url=definition.get('source_url'),
                    source_date=definition.get('source_date'),
                    reviewed_at=datetime.now(timezone.utc),
                    auto_resolve=definition.get('auto_resolve', True),
                    version=definition.get('version', 1),
                )
            )

        db.add(
            ImportBatch(
                source='wakyma_mock',
                filename='seed_dataset',
                status='completed',
                records_processed=len(OWNERS) + len(PETS),
                records_failed=0,
                finished_at=datetime.now(timezone.utc),
            )
        )
        db.commit()
        rebuild_alerts(db)
        logger.info('seed_completed')
    finally:
        db.close()


if __name__ == '__main__':
    seed()
