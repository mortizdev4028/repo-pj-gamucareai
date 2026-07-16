"""RAG chat endpoint and conversation persistence."""
from __future__ import annotations

import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.database import get_db
from app.dependencies import get_current_user, require_roles
from app.models import ChatMessage, ChatSession, Pet, PetPlanSubscription, SubscriptionService, User
from app.schemas import ChatRequest, ChatResponse, SourceResponse
from app.services.ollama import OllamaUnavailable
from app.observability.metrics import VETIA_DURATION, VETIA_REQUESTS
from app.services.payments import payment_values
from app.services.subscriptions import refresh_subscription_status
from app.services.rag import RagService

router = APIRouter(
    prefix='/chat',
    tags=['chat'],
    dependencies=[Depends(require_roles('clinic', 'staff', 'owner'))],
)
settings = get_settings()


def verify_pet_access(db: Session, user: User, pet_id) -> None:
    """Check optional pet context without exposing another owner's records."""
    if pet_id is None:
        return
    pet = db.get(Pet, pet_id)
    if pet is None or not pet.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Mascota no encontrada')
    if user.role == 'owner' and (user.owner is None or not user.owner.is_active or pet.owner_id != user.owner.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='No puedes consultar esta mascota')


def verify_scope_access(user: User, scope: str) -> None:
    """Reserve cross-patient retrieval while allowing owners to ask about their pets."""
    if scope == 'clinical' and user.role not in ('clinic', 'staff'):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='El analisis de historiales esta reservado al personal de la clinica',
        )


def load_authorised_pet(db: Session, user: User, pet_id) -> Pet:
    """Load all data needed by the pet assistant after ownership validation."""
    if pet_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Selecciona una mascota para realizar esta consulta',
        )
    verify_pet_access(db, user, pet_id)
    statement = (
        select(Pet)
        .where(Pet.id == pet_id)
        .options(
            selectinload(Pet.clinical_events),
            selectinload(Pet.risk_alerts),
            selectinload(Pet.subscriptions).selectinload(PetPlanSubscription.health_plan),
            selectinload(Pet.subscriptions)
            .selectinload(PetPlanSubscription.services)
            .selectinload(SubscriptionService.plan_service),
        )
    )
    pet = db.scalar(statement)
    if pet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Mascota no encontrada')
    return pet


def pet_context(pet: Pet, owner_view: bool) -> str:
    """Build a safe, deterministic context before asking the language model."""
    lines = [
        f'Mascota: {pet.name}.',
        f'Especie: {pet.species}. Raza: {pet.breed}.',
        f'Fecha de nacimiento: {pet.birth_date.isoformat()}. Sexo: {pet.sex}.',
        f'Peso actual: {float(pet.weight_kg):.1f} kg. Esterilizado: {"si" if pet.neutered else "no"}.',
        f'Alergias registradas: {pet.allergies or "ninguna"}.',
        f'Antecedentes registrados: {pet.chronic_conditions or "ninguno"}.',
    ]

    for item in pet.subscriptions:
        refresh_subscription_status(item)
    subscription = next(
        (item for item in pet.subscriptions if item.status in ('active', 'expiring')),
        next(
            (item for item in pet.subscriptions if item.status == 'scheduled'),
            max(pet.subscriptions, key=lambda item: item.end_date, default=None),
        ),
    )
    if subscription is None:
        lines.append('Plan de salud: no tiene un plan registrado.')
    else:
        payment = payment_values(subscription)
        lines.extend(
            [
                f'Plan de salud: {subscription.health_plan.name}.',
                f'Vigencia: {subscription.start_date.isoformat()} a {subscription.end_date.isoformat()}.',
                f'Estado del plan: {subscription.status}.',
                f'Pago: {"pagado" if payment["payment_status"] == "paid" else "pendiente a plazos"}; modalidad {"pago completo" if payment["payment_mode"] == "single" else "pago a plazos"}; '
                f'{payment["installments_paid"]} de {payment["installments_total"]} cuotas pagadas.',
                f'Importe total: {payment["total_amount"]} EUR. Pagado: {payment["amount_paid"]} EUR. '
                f'Pendiente: {payment["amount_remaining"]} EUR.',
                f'Estado de renovacion: {subscription.renewal_status}.',
            ]
        )
        upcoming = next(
            (item for item in pet.subscriptions if item.status == 'scheduled' and item.id != subscription.id),
            None,
        )
        if upcoming is not None:
            lines.append(
                f'Proximo plan programado: {upcoming.health_plan.name}, desde {upcoming.start_date.isoformat()} '
                f'hasta {upcoming.end_date.isoformat()}.'
            )
        pending = [
            item for item in subscription.services
            if item.status in ('pending', 'upcoming', 'overdue')
            and item.plan_service.service_mode not in ('discount', 'benefit')
        ]
        if pending:
            lines.append('Prestaciones pendientes o proximas:')
            for item in sorted(pending, key=lambda value: value.scheduled_date or subscription.end_date)[:20]:
                lines.append(
                    f'- {item.plan_service.name}: estado {item.status}; '
                    f'fecha prevista {item.scheduled_date.isoformat() if item.scheduled_date else "sin fecha"}.'
                )
        else:
            lines.append('Prestaciones pendientes o proximas: ninguna registrada.')

    events = sorted(pet.clinical_events, key=lambda item: item.event_date, reverse=True)
    if owner_view:
        events = [item for item in events if item.visible_to_owner]
    lines.append('Historial autorizado mas reciente:')
    for event in events[:20]:
        detail = f'- {event.event_date.date().isoformat()} | {event.title}: {event.description}'
        if event.diagnosis:
            detail += f' Diagnostico registrado: {event.diagnosis}.'
        if event.treatment:
            detail += f' Tratamiento registrado: {event.treatment}.'
        lines.append(detail)
    if not events:
        lines.append('- No hay eventos visibles registrados.')

    if pet.risk_alerts:
        lines.append('Avisos preventivos activos:')
        for alert in sorted(pet.risk_alerts, key=lambda item: item.generated_at, reverse=True)[:10]:
            lines.append(f'- {alert.title}: {alert.description}')
    return '\n'.join(lines)


@router.post('/ask', response_model=ChatResponse)
async def ask(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ChatResponse:
    """Answer a public-document or internal-clinical RAG question."""
    verify_scope_access(user, payload.scope)
    pet = load_authorised_pet(db, user, payload.pet_id) if payload.scope == 'pet' else None
    if payload.scope != 'pet':
        verify_pet_access(db, user, payload.pet_id)

    if payload.session_id:
        session = db.get(ChatSession, payload.session_id)
        if session is None or session.user_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Conversacion no encontrada')
        if session.pet_id != payload.pet_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail='Inicia una conversacion nueva al cambiar de mascota',
            )
    else:
        session = ChatSession(user_id=user.id, pet_id=payload.pet_id)
        db.add(session)
        db.flush()

    previous_messages = db.scalars(
        select(ChatMessage)
        .where(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at.desc())
        .limit(6)
    ).all()
    history = [
        {'role': message.role, 'content': message.content}
        for message in reversed(previous_messages)
    ]

    db.add(ChatMessage(session_id=session.id, role='user', content=payload.question))
    started = time.perf_counter()
    try:
        rag = RagService()
        if payload.scope == 'pet' and pet is not None:
            answer, chunks, grounded = await rag.answer_pet(
                payload.question,
                pet_id=pet.id,
                pet_name=pet.name,
                structured_context=pet_context(pet, owner_view=user.role == 'owner'),
                owner_visible_only=user.role == 'owner',
                history=history,
            )
        else:
            answer, chunks, grounded = await rag.answer(
                payload.question,
                scope=payload.scope,
                history=history,
            )
        model_name = settings.ollama_chat_model if grounded else None
    except OllamaUnavailable as exc:
        VETIA_REQUESTS.labels(payload.scope, 'unavailable').inc()
        VETIA_DURATION.labels(payload.scope).observe(time.perf_counter() - started)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except Exception as exc:
        VETIA_REQUESTS.labels(payload.scope, 'error').inc()
        VETIA_DURATION.labels(payload.scope).observe(time.perf_counter() - started)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='El asistente documental no esta disponible. Comprueba Qdrant y la ingesta.',
        ) from exc

    duration_seconds = time.perf_counter() - started
    VETIA_REQUESTS.labels(payload.scope, 'grounded' if grounded else 'no_context').inc()
    VETIA_DURATION.labels(payload.scope).observe(duration_seconds)
    elapsed = int(duration_seconds * 1000)
    source_payload = [
        {
            'title': chunk.title,
            'source': chunk.source,
            'url': chunk.url,
            'category': chunk.category,
            'score': round(chunk.score, 4),
            'dense_score': round(chunk.dense_score, 4),
            'citation_id': chunk.citation_id,
            'content_type': chunk.content_type,
            'document_id': chunk.document_id,
            'country': chunk.country,
            'language': chunk.language,
            'trust_level': chunk.trust_level,
            'tags': chunk.tags,
            'pet_id': chunk.pet_id,
            'pet_name': chunk.pet_name,
            'breed': chunk.breed,
            'species': chunk.species,
            'event_date': chunk.event_date,
            'event_type': chunk.event_type,
        }
        for chunk in chunks
    ]
    db.add(
        ChatMessage(
            session_id=session.id,
            role='assistant',
            content=answer,
            sources=source_payload,
            model_name=model_name,
            response_time_ms=elapsed,
        )
    )
    session.last_activity_at = datetime.now(timezone.utc)
    db.commit()

    return ChatResponse(
        session_id=session.id,
        answer=answer,
        sources=[SourceResponse(**item) for item in source_payload],
        model_name=model_name,
        response_time_ms=elapsed,
        grounded=grounded,
        diagnostics=rag.last_diagnostics.as_dict(),
    )
