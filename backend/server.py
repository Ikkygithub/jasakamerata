from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
import os, logging
from core import client
from seed import seed_data
from storage import init_storage
import auth
from routers import catalog, bookings, chat, customer, photographer, admin, payments

logging.basicConfig(level=logging.INFO)
app = FastAPI(title="Jasakamerata API")
api = APIRouter(prefix="/api")
for r in [catalog.router, auth.router, bookings.router, chat.router, customer.router, photographer.router, admin.router, payments.router]:
    api.include_router(r)
app.include_router(api)

origins = os.environ.get("CORS_ORIGINS", "*").split(",")
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=[] if "*" in origins else origins, allow_origin_regex=".*" if "*" in origins else None, allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
async def startup():
    await seed_data()
    init_storage()
    await payments.init_indexes()


@app.on_event("shutdown")
async def shutdown():
    client.close()
