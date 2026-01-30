from fastapi.responses import JSONResponse

def handle_exception(exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": str(exc), "type": exc.__class__.__name__}
    )
