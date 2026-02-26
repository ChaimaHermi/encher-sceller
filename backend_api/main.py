import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from backend_api.routers.upload_router import router as upload_router
from backend_api.routers.auth_router import router as auth_router
from backend_api.routers.listings_router import router as listings_router
from backend_api.database.mongo import connect_to_mongo, close_mongo_connection

app = FastAPI(title="Sealed Auction API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    await connect_to_mongo()

@app.on_event("shutdown")
async def shutdown():
    await close_mongo_connection()

app.include_router(auth_router, prefix="/api")
app.include_router(upload_router, prefix="/api")
app.include_router(listings_router, prefix="/api")

UPLOADS_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads")
if os.path.isdir(UPLOADS_DIR):
    app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")