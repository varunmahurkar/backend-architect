from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import os
from app.api.routes.auth import router as auth_router
from app.api.routes.chat import router as chat_router
from app.api.routes.crawler import router as crawler_router
from app.api.routes.conversations import router as conversations_router

app = FastAPI(
    title="Backend Architect API",
    description="A FastAPI backend service",
    version="1.0.0"
)

# CORS Configuration - Allow frontend origins
# Using wildcard patterns for development flexibility
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "https://localhost:3000",
    "https://127.0.0.1:3000",
    os.getenv("FRONTEND_URL", "http://localhost:3000"),
]

# Add any additional origins from environment
additional_origins = os.getenv("ALLOWED_ORIGINS", "").split(",")
origins.extend([o.strip() for o in additional_origins if o.strip()])

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH", "HEAD"],
    allow_headers=[
        "Accept",
        "Accept-Language",
        "Content-Type",
        "Content-Language",
        "Authorization",
        "X-Requested-With",
        "Origin",
        "Access-Control-Request-Method",
        "Access-Control-Request-Headers",
    ],
    expose_headers=["*"],
    max_age=86400,  # 24 hours preflight cache
)


@app.options("/{rest_of_path:path}")
async def preflight_handler(request: Request, rest_of_path: str):
    """Handle preflight OPTIONS requests explicitly for CORS."""
    return JSONResponse(
        content={"message": "OK"},
        headers={
            "Access-Control-Allow-Origin": request.headers.get("origin", "*"),
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
            "Access-Control-Allow-Headers": "Accept, Accept-Language, Content-Type, Authorization, X-Requested-With",
            "Access-Control-Max-Age": "86400",
        }
    )

# Include routers
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(crawler_router)
app.include_router(conversations_router)

@app.get("/")
def read_root():
    return {"message": "Backend Architect API is running!", "status": "healthy"}

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "backend-architect"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="127.0.0.1", port=port, reload=True)