from fastapi import FastAPI
from app.config import settings
from app.database import init_db
from app.middleware.error_handler import global_exception_handler
from app.routers import auth, providers, patients, visits, treatments, treatment_plans, audit

# Validate configuration on startup
settings.validate()

app = FastAPI(
    title="Patient Care EMR",
    description="HIPAA-compliant Electronic Medical Records API",
    version="1.0.0",
)

# Register global exception handler
app.add_exception_handler(Exception, global_exception_handler)

# Initialize database
init_db()

# Include routers
app.include_router(auth.router)
app.include_router(providers.router)
app.include_router(patients.router)
app.include_router(visits.router)
app.include_router(treatments.router)
app.include_router(treatment_plans.router)
app.include_router(audit.router)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
