from fastapi import FastAPI

app = FastAPI(title="Night Sky Digest")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
