# Cumplimiento de APIs externas — InkScroller Backend

> **Última actualización:** Abril 2026  
> **Alcance:** Backend FastAPI — capa proxy para MangaDex y Jikan/MAL  
> **Responsable:** Equipo InkScroller

---

## Tabla de contenidos

1. [Propósito](#1-propósito)
2. [MangaDex API](#2-mangadex-api)
3. [Jikan API / MyAnimeList](#3-jikan-api--myanimelist)
4. [Reglas compartidas](#4-reglas-compartidas)
5. [Proceso de Takedown](#5-proceso-de-takedown)
6. [Registro de revisión](#6-registro-de-revisión)

---

## 1. Propósito

Este documento establece las reglas de cumplimiento legal y ético para el uso de APIs de terceros dentro del backend de InkScroller. Su objetivo es garantizar que el proyecto:

- Respete los Términos de Servicio (ToS) de cada API.
- No monetice contenido que pertenece a terceros.
- Proporcione la atribución requerida a autores, grupos de scanlation y plataformas fuente.
- Minimice el riesgo legal ante eventuales DMCA o solicitudes de takedown.

> **Principio rector:** El backend actúa exclusivamente como **proxy de lectura**. No almacena ni redistribuye contenido de forma masiva. Todo el contenido se obtiene en tiempo real y se sirve al cliente Flutter autenticado.

---

## 2. MangaDex API

### 2.1 Fuente oficial

- **API:** [MangaDex API v5](https://api.mangadex.org)
- **Documentación oficial:** [api.mangadex.org/docs](https://api.mangadex.org/docs)
- **Términos de Servicio:** [mangadex.org/about/terms-of-service](https://mangadex.org/about/terms-of-service)

### 2.2 Reglas de uso

| # | Regla | Estado |
|---|-------|--------|
| 1 | **No monetización directa del contenido API.** Ninguna funcionalidad del backend ni del cliente puede estar detrás de un paywall usando contenido de MangaDex. | ✅ Cumplido — el backend es proxy gratuito |
| 2 | **Proxy backend obligatorio.** El cliente Flutter NO llama a MangaDex directamente. Toda solicitud pasa por el backend InkScroller. | ✅ Cumplido — Flutter solo llama a nuestro backend |
| 3 | **Atribución a MangaDex.** Toda interfaz que muestre contenido debe referenciar la fuente MangaDex. | ⚠️ Pendiente — agregar atribución visible en el cliente |
| 4 | **Atribución a grupos de scanlation.** Los capítulos pertenecen a grupos de scanlation. Deben ser visibles en los datos del capítulo. | ⚠️ Verificar — los `relationships` del capítulo contienen `scanlation_group` |
| 5 | **Respetar rate limits.** La API pública tiene límites estrictos (ver §2.4). | ✅ Parcial — caché de 5 min implementado |
| 6 | **No redistribución masiva.** No exponer endpoints que descarguen catálogos completos de imágenes o bulk chapter dumps. | ✅ Cumplido — solo se sirven URLs, no binarios |

### 2.3 Atribución requerida

Para cada capítulo servido, el backend debe incluir (o el cliente debe mostrar) los siguientes datos:

```json
{
  "chapter_id": "...",
  "scanlation_group": "Nombre del grupo de scanlation",
  "source": "MangaDex",
  "source_url": "https://mangadex.org/chapter/{chapter_id}"
}
```

**Acción requerida:** Extender el modelo `ChapterResponse` para incluir el campo `scanlation_group` extraído de `relationships[type=scanlation_group].attributes.name`.

### 2.4 Rate limits

| Tipo | Límite | Manejo actual |
|------|--------|---------------|
| API pública (sin auth) | ~5 req/s por IP | Caché in-memory 5 min por recurso |
| HTTP 429 (Too Many Requests) | Bloqueo temporal | ⚠️ Sin retry con backoff exponencial |
| MangaDex@Home (imágenes) | Variable por CDN node | Solo se sirven URLs — las imágenes las descarga el cliente |

**Acciones recomendadas:**
1. Implementar retry con backoff exponencial ante HTTP 429.
2. Agregar header `User-Agent: InkScroller/1.0 (contact@inkscroller.app)` en todas las solicitudes a MangaDex.
3. Evaluar autenticación de API para mayor rate limit.

### 2.5 Contenido prohibido

- No cachear imágenes de capítulos en el servidor (solo URLs).
- No servir contenido marcado como `contentRating: erotica` o `pornographic` sin verificación de edad.
- No crear funcionalidad de descarga masiva (bulk download).

---

## 3. Jikan API / MyAnimeList

### 3.1 Fuente oficial

- **API:** [Jikan v4](https://api.jikan.moe/v4)
- **Documentación:** [docs.api.jikan.moe](https://docs.api.jikan.moe)
- **Términos MyAnimeList:** [myanimelist.net/about/terms_of_use](https://myanimelist.net/about/terms_of_use)

> **Importante:** Jikan es un scraper NO OFICIAL de MyAnimeList. No es una API oficial de MAL. Su estabilidad y disponibilidad no están garantizadas.

### 3.2 Reglas de uso

| # | Regla | Estado |
|---|-------|--------|
| 1 | **Sin afiliación con MAL/Jikan.** InkScroller no es oficial ni está afiliado a MyAnimeList ni a Jikan. Esto debe ser visible en la UI. | ⚠️ Agregar disclaimer en el cliente |
| 2 | **Respetar rate limits de Jikan.** Jikan tiene límites muy restrictivos (ver §3.3). | ✅ Parcial — caché 5 min reduce llamadas |
| 3 | **Solo enriquecimiento, nunca fuente primaria.** Jikan solo se usa para enriquecer datos que MangaDex no provee (score, rank, genres). | ✅ Cumplido — lógica de enriquecimiento implementada |
| 4 | **Evitar redistribución masiva de datos de MAL.** No exponer endpoints que devuelvan catálogos de MAL. | ✅ Cumplido — solo se enriquece por ID de manga |
| 5 | **Feature flag / fallback recomendado.** Si Jikan no está disponible, el sistema debe degradar gracefully. | ⚠️ Implementar — actualmente un fallo de Jikan puede propagar error |

### 3.3 Rate limits de Jikan

| Tipo | Límite | Manejo actual |
|------|--------|---------------|
| Solicitudes por segundo | 3 req/s | Caché in-memory 5 min mitiga esto |
| Solicitudes por minuto | 60 req/min | Caché in-memory cubre la mayoría |
| HTTP 429 | Bloqueo 1 min | ⚠️ Sin manejo explícito |

**Acciones recomendadas:**
1. Envolver la llamada a Jikan en un bloque `try/except` que devuelva el manga sin enriquecimiento si Jikan falla (degradación graceful).
2. Implementar feature flag `ENABLE_JIKAN_ENRICHMENT=true/false` en `.env`.
3. Loggear warnings cuando Jikan retorna 429.

### 3.4 Ejemplo de implementación con fallback

```python
# app/services/manga_service.py

async def _enrich_with_jikan(self, manga: dict) -> dict:
    """Enriquece datos de manga con Jikan. Si falla, devuelve manga sin enriquecer."""
    if not settings.ENABLE_JIKAN_ENRICHMENT:
        return manga
    try:
        jikan_data = await self.jikan_client.search_manga(manga["title"])
        return _merge_jikan_data(manga, jikan_data)
    except Exception as e:
        logger.warning(f"Jikan enrichment failed for '{manga['title']}': {e}")
        return manga  # fallback: manga sin enriquecimiento
```

---

## 4. Reglas compartidas

### 4.1 Identificación del cliente

Todos los clientes HTTP del backend deben incluir un `User-Agent` identificatorio:

```python
headers = {
    "User-Agent": "InkScroller-Backend/1.0 (contact@inkscroller.app)"
}
```

### 4.2 No cacheo de binarios

- El backend **solo cachea JSON** (metadatos, URLs de imágenes).
- Las imágenes se entregan al cliente Flutter como URLs, no como binarios.
- Esto evita actuar como CDN de contenido de terceros.

### 4.3 Sin autenticación falsificada

- No usar credenciales de terceros (cuentas de MAL, cookies de MangaDex) para eludir rate limits.
- Si se necesita mayor cuota, utilizar los programas de API oficial.

### 4.4 Datos de usuarios

- No enviar datos personales de usuarios a MangaDex ni a Jikan.
- Las solicitudes proxy no deben incluir el Firebase UID del usuario en las llamadas upstream.

---

## 5. Proceso de Takedown

En caso de recibir una solicitud de DMCA, takedown, o aviso legal de MangaDex, MAL o cualquier titular de derechos:

### 5.1 Pasos inmediatos (< 24 hs)

1. **Deshabilitar el endpoint afectado** mediante feature flag o despliegue urgente.
2. **No eliminar logs** — conservar para análisis legal.
3. **Notificar al equipo** responsable del proyecto.

### 5.2 Pasos secundarios (< 72 hs)

4. Identificar qué contenido específico está sujeto a la solicitud.
5. Purgar el caché in-memory de los recursos afectados.
6. Responder a la solicitud por los canales legales indicados.
7. Documentar el incidente en este archivo bajo `§6 Registro de revisión`.

### 5.3 Contacto

- **MangaDex:** [mangadex.org/about/contact](https://mangadex.org/about/contact)
- **Jikan:** [github.com/jikan-me/jikan](https://github.com/jikan-me/jikan/issues)
- **MAL soporte:** [myanimelist.net/support](https://myanimelist.net/support)

---

## 6. Registro de revisión

| Fecha | Versión | Cambio | Autor |
|-------|---------|--------|-------|
| 2026-04-07 | 1.0 | Creación inicial del documento | InkScroller Team |
