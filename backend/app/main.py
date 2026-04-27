from fastapi import FastAPI

app = FastAPI(title="A Share Strategy Assistant")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
