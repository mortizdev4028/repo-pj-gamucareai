"""Import a mock Wakyma JSON or CSV export from the command line."""
from __future__ import annotations

import argparse

from sqlalchemy import select

from app.database import SessionLocal
from app.integrations.wakyma.adapter import MockWakymaAdapter
from app.models import User


def main() -> None:
    parser = argparse.ArgumentParser(description='Importar datos ficticios de Wakyma')
    parser.add_argument('path', nargs='?', default='/app/data/seed/wakyma_mock.json')
    parser.add_argument('--user', default='clinic@gamucare.local', help='Usuario que quedara en la auditoria')
    args = parser.parse_args()

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == args.user))
        if user is None:
            raise SystemExit(f'No existe el usuario de auditoria {args.user}')
        result = MockWakymaAdapter().import_data(db, args.path, user.id)
    print(
        f'Propietarios creados: {result.owners_created}; actualizados: {result.owners_updated}; '
        f'mascotas creadas: {result.pets_created}; actualizadas: {result.pets_updated}; '
        f'eventos creados: {result.events_created}; actualizados: {result.events_updated}; '
        f'errores: {result.records_failed}'
    )


if __name__ == '__main__':
    main()
