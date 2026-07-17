from fastapi import FastAPI


def create_app() -> FastAPI:
    return FastAPI(title="Precedent API")


app = create_app()
