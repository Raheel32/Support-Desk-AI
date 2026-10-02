from fastapi import FastAPI

app = FastAPI(title="Support Desk AI")


@app.get("/")
def home():
    return {
        "message": "Welcome to Support Desk AI"
    }


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "Support Desk AI"
    }