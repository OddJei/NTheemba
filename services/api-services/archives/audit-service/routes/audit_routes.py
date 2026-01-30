from fastapi import APIRouter
from controllers.audit_controller import ingest_events, get_audit, query_audits

router = APIRouter()

router.post('/log')(ingest_events)
router.get('/{audit_id}')(get_audit)
router.get('/')(query_audits)
