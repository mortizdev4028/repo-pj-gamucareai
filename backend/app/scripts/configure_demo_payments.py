"""Apply varied payment states to the existing fictitious subscriptions."""
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import SessionLocal
from app.models import Pet, PetPlanSubscription
from app.seed import demo_payment_terms
from app.services.subscriptions import generate_installments


def configure() -> None:
    """Update only records belonging to the deterministic Wakyma demo dataset."""
    db = SessionLocal()
    updated = 0
    try:
        subscriptions = db.scalars(
            select(PetPlanSubscription)
            .join(Pet)
            .where(Pet.external_id.like('WK-PET-%'))
            .options(
                selectinload(PetPlanSubscription.pet),
                selectinload(PetPlanSubscription.health_plan),
                selectinload(PetPlanSubscription.installments),
            )
            .order_by(Pet.external_id)
        ).all()
        for index, subscription in enumerate(subscriptions):
            values = demo_payment_terms(
                subscription.health_plan,
                index,
                subscription.start_date,
                subscription.end_date,
            )
            for field, value in values.items():
                setattr(subscription, field, value)
            generate_installments(subscription)
            updated += 1
        db.commit()
        print(f'Estados de pago configurados: {updated}')
    finally:
        db.close()


if __name__ == '__main__':
    configure()
