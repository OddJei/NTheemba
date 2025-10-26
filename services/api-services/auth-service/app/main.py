from fastapi import FastAPI
from app.api import auth_routes, otp_routes, session_routes
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI(
    title="Auth Service",
    description="Authentication and Authorization microservice",
    version="1.0.0"
)


# Register routers
app.include_router(auth_routes.router, prefix="/auth", tags=["auth"])
app.include_router(otp_routes.router, prefix="/otp", tags=["otp"])
app.include_router(session_routes.router, prefix="/sessions", tags=["sessions"])

# Health check
@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.on_event("startup")
async def startup():
    Instrumentator().instrument(app).expose(app)

