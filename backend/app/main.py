from fastapi import FastAPI

app = FastAPI(title="AI Study Assistant")


@app.get("/health")
def health():
    return {"status": "ok"}