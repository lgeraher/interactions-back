from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from routes.interaction import router as interaction_router
from database import client

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    print("Starting up...")
    yield  # Application runs during this time
    # Shutdown logic
    print("Shutting down gracefully...")
    client.close()
    print("Database connection closed.")

app = FastAPI(lifespan=lifespan)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://interactions.itexico.com", "http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register the routes without a prefix
app.include_router(interaction_router, tags=["Interactions"])

@app.get("/")
async def root():
    return {"message": "Welcome to the Interaction Tracker API"}
