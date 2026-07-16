"""Create detailed payment schedules for subscriptions created before v0.5."""
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import SessionLocal
from app.models import PetPlanSubscription
from app.services.subscriptions import generate_installments


def main() -> None:
    db = SessionLocal()
    created = 0
    try:
        subscriptions = list(
            db.scalars(
                select(PetPlanSubscription).options(
                    selectinload(PetPlanSubscription.health_plan),
                    selectinload(PetPlanSubscription.installments),
                )
            ).unique().all()
        )
        for subscription in subscriptions:
            if subscription.installments:
                continue
            generate_installments(subscription)
            created += len(subscription.installments)
        db.commit()
        print(f'Cuotas creadas: {created}')
    finally:
        db.close()


if __name__ == '__main__':
    main()
