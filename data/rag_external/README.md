# Documentos externos del RAG

Este directorio se rellena con `scripts/download-rag-sources.ps1`. Los documentos
oficiales no se incluyen en el ZIP para evitar redistribuir contenido de terceros
y para que cada descarga proceda de la version publicada por el organismo.

Cada fichero descargado tiene un sidecar `<nombre>.meta.json` con URL, SHA-256,
tamano, fecha de descarga y metadatos de indexacion. Despues de descargar hay que
reconstruir Qdrant con `python -m app.rag.ingest`.
