# Formato de importacion Wakyma simulado

El conector acepta JSON y CSV UTF-8 de hasta 5 MB. Todos los datos utilizados en el TFM son ficticios.

## JSON 2.0

La raiz incluye `source: wakyma_mock`, `schema_version: 2.0` y las listas `owners`, `pets` y `clinical_events`.

## CSV 2.0

El CSV utiliza una fila por entidad y una columna obligatoria `entity_type` con uno de estos valores:

- `owner`
- `pet`
- `clinical_event`

Las relaciones se resuelven mediante `owner_external_id` y `pet_external_id`.

## Comportamiento

- La validacion previa no modifica clientes, mascotas ni historiales.
- La importacion actualiza registros existentes mediante `external_id`.
- Los errores se registran por fila y no impiden procesar registros independientes validos.
- Los propietarios nuevos reciben una contrasena temporal que solo se devuelve en la respuesta inmediata.
- Tras una importacion real, las mascotas afectadas se reindexan en Qdrant y recalculan sus avisos preventivos en segundo plano.
