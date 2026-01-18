from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
from app.api.routes.auth import router as auth_router

app = FastAPI(
    title="Backend Architect API",
    description="A FastAPI backend service",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include authentication routes
app.include_router(auth_router)

@app.get("/")
def read_root():
    return {"message": "Backend Architect API is running!", "status": "healthy"}

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "backend-architect"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="127.0.0.1", port=port, reload=True)