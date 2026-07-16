# Fuentes documentales iniciales del RAG

Fecha de revision inicial: 13 de julio de 2026.

- Union Europea, Your Europe: viajes con mascotas y otros animales en la UE.
  https://europa.eu/youreurope/citizens/travel/carry/pets-and-other-animals/index_es.htm
- Ministerio de Agricultura, Pesca y Alimentacion: viajar con perros, gatos y hurones.
  https://www.mapa.gob.es/es/ganaderia/temas/comercio-exterior-ganadero/desplazamiento-animales-compania/viajar-perros-gatos-hurones
- WSAVA: pautas 2024 para la vacunacion de perros y gatos, version en espanol.
  https://wsava.org/wp-content/uploads/2024/05/ESP.-J-of-Small-Animal-Practice-2024-Squires-2024-guidelines-for-the-vaccination-of-dogs-and-cats-compiled-by-the.pdf
- ESCCAP: GL9, control de parasitos en mascotas viajeras e importadas.
  https://www.esccap.org/guidelines/gl9/

Los Markdown incluidos en `data/rag` son resumenes breves elaborados para la
demostracion. No sustituyen los documentos oficiales. En la siguiente iteracion
se descargaran, versionaran y evaluaran documentos completos cuando sus
condiciones de uso lo permitan.

## Historiales clinicos del MVP

Las fichas y eventos indexados desde PostgreSQL son completamente ficticios y
se utilizan solo para demostrar recuperacion semantica y deteccion exploratoria
de recurrencias. No constituyen una fuente cientifica ni datos de pacientes
reales.

## Fuentes anadidas para los avisos preventivos 0.6.0

- AAHA: Senior Care Guidelines for Dogs and Cats, 2023.
  https://www.aaha.org/resources/2023-aaha-senior-care-guidelines-for-dogs-and-cats/
- WSAVA: Global Nutrition Guidelines and Toolkit.
  https://wsava.org/Global-Guidelines/Global-Nutrition-Guidelines/
- University of Cambridge: BOAS Research Group.
  https://www.vet.cam.ac.uk/boas/about-boas
- International Renal Interest Society: IRIS Guidelines.
  https://www.iris-kidney.com/iris-guidelines-1
- ESCCAP: guias europeas para el control de parasitos.
  https://www.esccap.org/guidelines/

Estas referencias justifican el tema que debe revisarse, no un diagnostico
individual. Los umbrales de recurrencia y variacion de peso son criterios
operativos del MVP y deben validarse por profesionales antes de un uso real.

## Fuentes incorporadas en 0.7.0

- WSAVA Vaccination Guidelines Group: vacunacion de perros y gatos.
- Ministerio de Agricultura, Pesca y Alimentacion: viajes desde Espana y requisitos de salida o regreso.
- Union Europea / Your Europe: viajes dentro de la UE y entrada desde terceros paises.
- ESCCAP GL1: control de parasitos en perros y gatos.
- ESCCAP GL5 y GL9: enfermedades transmitidas por vectores y riesgos asociados a viajes.
- WSAVA Global Nutrition Committee: peso, condicion corporal y condicion muscular.
- AAHA Senior Care Guidelines: seguimiento preventivo de pacientes senior.
- International Renal Interest Society: principios de estadificacion y seguimiento renal.

Los ficheros Markdown contienen resumenes redactados para el proyecto y enlaces a la fuente original. Cada documento incorpora fecha de revision, categoria, ambito, audiencia y nivel de confianza.

## Gobierno documental incorporado en 0.14.0

La version 0.14.0 incorpora `data/rag_sources/sources.json`, un catalogo
versionado de fuentes externas. El repositorio no incluye los PDF ni las paginas
HTML completas: `scripts/download-rag-sources.ps1` las obtiene desde el organismo
oficial y guarda un sidecar con URL de descarga, fecha, tipo MIME, tamano y
SHA-256.

Catalogo inicial:

- WSAVA, pautas de vacunacion 2024 en espanol.
- AAHA, Senior Care Guidelines 2023.
- ESCCAP, GL5 sobre enfermedades transmitidas por vectores.
- FEDIAF, Nutritional Guidelines 2025.
- IRIS, sistema de estadificacion de enfermedad renal cronica.
- Union Europea, requisitos para viajar con mascotas.
- MAPA, desplazamiento de perros, gatos y hurones.

Los ficheros descargados quedan en `data/rag_external` y se indexan junto con los
resumenes locales. La aplicacion conserva la procedencia, pero no garantiza que
una URL siga vigente ni que la guia sea aplicable a un paciente concreto.
