# ADR-008: Separar la integracion Wakyma mediante un adaptador normalizado

- Estado: aceptada
- Fecha: 2026-07-15

## Contexto

El proyecto necesita representar una integracion con Wakyma, pero el MVP no dispone de credenciales, contrato de API ni datos reales. Acoplar la logica de negocio a un formato supuesto haria dificil sustituirlo en el futuro.

## Decision

Se crea una frontera de integracion formada por tres etapas:

1. Parser de transporte: JSON o CSV ficticio.
2. Normalizacion y validacion: registros independientes de Wakyma.
3. Persistencia: actualizacion idempotente de las entidades internas por `external_id`.

El resultado de cada fila queda auditado. La interfaz real futura debera producir los mismos registros normalizados, sin cambiar los servicios de clientes, mascotas, historiales, RAG o alertas.

## Alternativas valoradas

### Importar directamente desde los routers

Descartada porque mezcla HTTP, validacion y SQL, dificulta las pruebas y obliga a reescribir la integracion cuando cambie el origen.

### Utilizar exclusivamente el formato interno de PostgreSQL

Descartada porque expone detalles de persistencia al sistema externo y reduce la capacidad de evolucionar el modelo.

### Crear ahora un cliente de API Wakyma no documentado

Descartada porque supondria inventar un contrato tecnico y presentar como real una integracion no verificada.

## Consecuencias positivas

- Sustitucion futura del fichero por una API real.
- Validacion previa sin efectos laterales.
- Importaciones repetibles e idempotentes.
- Trazabilidad por lote y por registro.
- Pruebas unitarias sin depender de servicios externos.

## Consecuencias negativas

- Se mantienen dos formatos de entrada en el MVP.
- El proceso sincrono no es apropiado para exportaciones masivas.
- La fusion de duplicados complejos sigue necesitando intervencion manual futura.
