"""Role-aware dashboard and CSV export endpoints."""
from __future__ import annotations

import csv
from io import StringIO
import time
import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from prometheus_client import Counter, Histogram
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_roles
from app.models import User
from app.schemas import DashboardResponse
from app.services.dashboard import build_dashboard

router = APIRouter(
    prefix='/dashboard',
    tags=['dashboard'],
    dependencies=[Depends(require_roles('clinic', 'staff', 'owner'))],
)

DASHBOARD_DURATION = Histogram(
    'gamucare_dashboard_generation_seconds',
    'Time used to calculate one role-aware dashboard',
    ['role'],
)
DASHBOARD_EXPORTS = Counter(
    'gamucare_dashboard_exports_total',
    'Number of dashboard CSV exports',
    ['role'],
)


def _build(
    db: Session,
    user: User,
    months: int,
    species: str | None,
    plan_id: uuid.UUID | None,
) -> DashboardResponse:
    started = time.perf_counter()
    try:
        return build_dashboard(db, user, months=months, species=species, plan_id=plan_id)
    finally:
        DASHBOARD_DURATION.labels(user.role).observe(time.perf_counter() - started)


@router.get('', response_model=DashboardResponse)
def dashboard(
    months: int = Query(default=6, ge=1, le=24),
    species: str | None = Query(default=None, pattern='^(dog|cat)$'),
    plan_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DashboardResponse:
    """Return operational, financial and preventive figures in the user's scope."""
    return _build(db, user, months, species, plan_id)


@router.get('/export.csv')
def export_dashboard(
    months: int = Query(default=6, ge=1, le=24),
    species: str | None = Query(default=None, pattern='^(dog|cat)$'),
    plan_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Export the exact dashboard scope as a semicolon-separated UTF-8 CSV."""
    data = _build(db, user, months, species, plan_id)
    output = StringIO()
    output.write('\ufeff')
    writer = csv.writer(output, delimiter=';', lineterminator='\n')
    writer.writerow(['GamuCare AI', 'Resumen de indicadores'])
    writer.writerow(['Generado', data.generated_at.isoformat()])
    writer.writerow(['Perfil', data.role_scope])
    writer.writerow(['Periodo (meses)', data.filters.get('months')])
    writer.writerow(['Especie', data.filters.get('species') or 'Todas'])
    writer.writerow([])
    writer.writerow(['Indicador', 'Valor'])
    for label, value in (
        ('Mascotas', data.pets_total),
        ('Planes activos', data.plans_active),
        ('Planes proximos a vencer', data.plans_expiring),
        ('Servicios pendientes', data.services_pending),
        ('Servicios vencidos', data.services_overdue),
        ('Mascotas con avisos', data.pets_with_alerts),
        ('Cumplimiento medio (%)', data.completion_average),
        ('Importe comprometido', data.financial.total_committed),
        ('Importe cobrado', data.financial.amount_collected),
        ('Importe pendiente', data.financial.amount_outstanding),
        ('Importe vencido', data.financial.overdue_amount),
    ):
        writer.writerow([label, value])

    writer.writerow([])
    writer.writerow(['Mes', 'Planes iniciados', 'Renovaciones', 'Servicios realizados', 'Avisos generados', 'Importe cobrado'])
    for item in data.monthly_trends:
        writer.writerow([
            item.month, item.plans_started, item.renewals, item.services_completed,
            item.alerts_generated, item.amount_collected,
        ])

    writer.writerow([])
    writer.writerow(['Proximas acciones', 'Mascota', 'Fecha', 'Estado', 'Detalle'])
    for item in data.upcoming_items:
        writer.writerow([item.title, item.pet_name, item.due_date, item.status, item.detail])

    DASHBOARD_EXPORTS.labels(user.role).inc()
    filename = f'gamucare-dashboard-{data.generated_at.date().isoformat()}.csv'
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type='text/csv; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )
