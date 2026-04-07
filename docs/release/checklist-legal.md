# Checklist Legal — Release InkScroller Backend

> **Propósito:** Validar el cumplimiento legal y de APIs antes de promover a producción.  
> **Usar en:** Cada release a `staging` y `prod`.  
> **Referencia:** [`docs/legal/api-compliance.md`](../legal/api-compliance.md)

---

## Regla GO / NO-GO

> **Un NO en cualquier ítem marcado con 🔴 bloquea el release.**  
> Los ítems 🟡 son advertencias — documentar la decisión si se omiten.

---

## Bloque 1 — MangaDex

| # | Ítem | Criticidad | Estado |
|---|------|-----------|--------|
| 1.1 | El backend actúa como proxy — Flutter **no** llama a MangaDex directamente | 🔴 BLOQUEANTE | ☐ |
| 1.2 | No se cachean binarios de imágenes en el servidor (solo URLs) | 🔴 BLOQUEANTE | ☐ |
| 1.3 | No existe endpoint de bulk download de capítulos | 🔴 BLOQUEANTE | ☐ |
| 1.4 | El caché in-memory está activo (TTL 5 min) para reducir llamadas a MangaDex | 🟡 ADVERTENCIA | ☐ |
| 1.5 | Todos los clientes HTTP incluyen header `User-Agent: InkScroller-Backend/...` | 🟡 ADVERTENCIA | ☐ |
| 1.6 | Existe manejo de HTTP 429 (retry con backoff o log de warning) | 🟡 ADVERTENCIA | ☐ |
| 1.7 | El contenido con `contentRating: erotica/pornographic` está filtrado o requiere verificación de edad | 🔴 BLOQUEANTE | ☐ |
| 1.8 | La respuesta de capítulos incluye o puede incluir `scanlation_group` para atribución | 🟡 ADVERTENCIA | ☐ |

## Bloque 2 — Jikan / MyAnimeList

| # | Ítem | Criticidad | Estado |
|---|------|-----------|--------|
| 2.1 | Jikan solo se usa como capa de enriquecimiento (no es fuente primaria) | 🔴 BLOQUEANTE | ☐ |
| 2.2 | Existe fallback graceful si Jikan retorna error o 429 | 🟡 ADVERTENCIA | ☐ |
| 2.3 | No se expone un endpoint que devuelva catálogos de MAL en bulk | 🔴 BLOQUEANTE | ☐ |
| 2.4 | El caché in-memory cubre las llamadas frecuentes a Jikan | 🟡 ADVERTENCIA | ☐ |
| 2.5 | Existe feature flag `ENABLE_JIKAN_ENRICHMENT` en `.env.example` | 🟡 ADVERTENCIA | ☐ |

## Bloque 3 — Seguridad y privacidad

| # | Ítem | Criticidad | Estado |
|---|------|-----------|--------|
| 3.1 | No se envían datos de usuarios (Firebase UID, email) a MangaDex ni Jikan | 🔴 BLOQUEANTE | ☐ |
| 3.2 | Las variables de entorno sensibles NO están hardcodeadas (revisar `.env` vs código) | 🔴 BLOQUEANTE | ☐ |
| 3.3 | El `.env` de producción no está en el repositorio | 🔴 BLOQUEANTE | ☐ |
| 3.4 | Firebase Admin SDK credentials están configuradas via env var, no en el repo | 🔴 BLOQUEANTE | ☐ |

## Bloque 4 — Atribución y disclaimers

| # | Ítem | Criticidad | Estado |
|---|------|-----------|--------|
| 4.1 | El README del backend menciona que NO hay afiliación con MangaDex ni MAL | 🟡 ADVERTENCIA | ☐ |
| 4.2 | Existe documentación de cumplimiento en `docs/legal/api-compliance.md` actualizada | 🟡 ADVERTENCIA | ☐ |
| 4.3 | El proceso de takedown (`docs/legal/api-compliance.md §5`) está definido y el equipo lo conoce | 🟡 ADVERTENCIA | ☐ |

## Bloque 5 — Operacional (pre-deploy)

| # | Ítem | Criticidad | Estado |
|---|------|-----------|--------|
| 5.1 | Tests de smoke pasan (`tests/test_app.py`) | 🔴 BLOQUEANTE | ☐ |
| 5.2 | Health check `/ping` responde correctamente en el entorno destino | 🔴 BLOQUEANTE | ☐ |
| 5.3 | Variables de entorno del entorno destino están configuradas en Cloud Run | 🔴 BLOQUEANTE | ☐ |
| 5.4 | Revisión de logs de las últimas 24 hs — sin errores críticos ni picos de 429 | 🟡 ADVERTENCIA | ☐ |

---

## Resultado final

```
Fecha de release: ___________
Entorno: ☐ staging  ☐ prod
Revisado por: ___________

Bloqueos encontrados (ítems 🔴 en NO):
- [ ] Ninguno → GO ✅
- [ ] (listar si los hay) → NO-GO ❌

Advertencias documentadas:
- (listar ítems 🟡 en NO con justificación)

Decisión final: ☐ GO  ☐ NO-GO
Firma: ___________
```

---

## Planned / TODO — Deuda técnica detectada

> Estos ítems fueron detectados durante auditoría de compliance (2026-04-07).
> **No están implementados aún.** Deben resolverse antes del primer release público.
> No borrar hasta que el ítem correspondiente esté implementado y verificado.

| # | Gap | Ítem relacionado en checklist | Repos | Prioridad |
|---|-----|-------------------------------|-------|-----------|
| P-1 | Exponer `scanlation_group` en respuestas de capítulos (el serializer no lo incluye actualmente) | 1.8 | `Inkscroller_backend` | Media |
| P-2 | Implementar retry con backoff exponencial ante HTTP 429 de MangaDex | 1.6 | `Inkscroller_backend` | Media |
| P-3 | Agregar fallback graceful en cliente Jikan — retornar datos parciales ante error o 429 | 2.2 | `Inkscroller_backend` | Media |
| P-4 | Agregar `ENABLE_JIKAN_ENRICHMENT=true` a `.env.example` y leerlo en el servicio Jikan | 2.5 | `Inkscroller_backend` | Baja |
| P-5 | *(Para Flutter)* Crear pantalla About/Créditos con disclaimer de no afiliación a MangaDex y MAL | 3.4 (flutter) | `inkscroller_flutter` | Media |

---

## Referencias

- [`docs/legal/api-compliance.md`](../legal/api-compliance.md) — reglas detalladas de cumplimiento
- [`docs/DEPLOYMENT.md`](../DEPLOYMENT.md) — proceso de deploy a Cloud Run
- [`docs/PROJECT_STATUS.md`](../PROJECT_STATUS.md) — estado actual del proyecto
