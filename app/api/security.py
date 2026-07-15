"""Unauthenticated security reporting endpoints."""

import json
import logging

from fastapi import APIRouter, Request as FastAPIRequest
from pydantic import BaseModel, Field, ValidationError
from starlette.responses import Response

logger = logging.getLogger(__name__)
router = APIRouter(tags=["security"])

_CSP_SAFE_FIELDS = {
    "effective-directive",
    "violated-directive",
    "disposition",
    "status-code",
    "line-number",
    "column-number",
}

_MAX_LOG_FIELD_LENGTH = 200


class CSPReportEnvelope(BaseModel):
    csp_report: dict[str, object] = Field(alias="csp-report")


def _sanitize(value: object) -> str:
    """Truncate and strip control chars from a loggable field value."""
    s = str(value)[:_MAX_LOG_FIELD_LENGTH]
    return s.replace("\n", " ").replace("\r", " ")


@router.post("/csp-report")
async def receive_csp_report(request: FastAPIRequest) -> Response:
    """Accept a browser CSP violation report.

    Accepts ``application/json`` and ``application/csp-report`` content types
    by parsing the raw body directly (browsers send ``application/csp-report``).
    Logs only allowlisted non-PII metadata.
    """
    # ponytail: telemetry input — discard bad payloads silently
    try:
        body = await request.body()
        data = json.loads(body)
        envelope = CSPReportEnvelope(**data)
    except (json.JSONDecodeError, ValidationError):
        return Response(status_code=204)

    report = envelope.csp_report
    safe_metadata = {
        field: _sanitize(report[field]) for field in _CSP_SAFE_FIELDS if field in report
    }

    if safe_metadata:
        parts = "; ".join(f"{k}={v}" for k, v in safe_metadata.items())
        logger.info("csp_report_received [%s]", parts)
    else:
        logger.info("csp_report_received [no safe metadata]")

    return Response(status_code=204)
