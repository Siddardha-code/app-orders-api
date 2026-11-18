import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from .metrics import REQUEST_COUNT, REQUEST_LATENCY
from .repo import OrderRepo, PostgresRepo
from .schemas import OrderIn, OrderOut

# Probe and scrape traffic is excluded so it does not distort the SLI.
EXCLUDED_PATHS = {"/metrics", "/healthz", "/readyz"}


def create_app(repo: OrderRepo | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        owned = None
        if repo is None:
            owned = PostgresRepo(os.environ["DATABASE_URL"])
            owned.open()
            app.state.repo = owned
        else:
            app.state.repo = repo
        yield
        if owned is not None:
            owned.close()

    app = FastAPI(title="orders-api", version="0.1.0", lifespan=lifespan)

    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next):
        if request.url.path in EXCLUDED_PATHS:
            return await call_next(request)
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            route = request.scope.get("route")
            path = route.path if route else "unmatched"
            REQUEST_COUNT.labels(request.method, path, str(status)).inc()
            REQUEST_LATENCY.labels(request.method, path).observe(
                time.perf_counter() - start
            )

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.get("/readyz")
    def readyz(request: Request):
        try:
            request.app.state.repo.ping()
        except Exception:
            raise HTTPException(status_code=503, detail="database unavailable")
        return {"status": "ready"}

    @app.get("/metrics")
    def metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.post("/orders", response_model=OrderOut, status_code=201)
    def create_order(order: OrderIn, request: Request):
        return request.app.state.repo.create(order.item, order.quantity)

    @app.get("/orders/{order_id}", response_model=OrderOut)
    def get_order(order_id: int, request: Request):
        order = request.app.state.repo.get(order_id)
        if order is None:
            raise HTTPException(status_code=404, detail="order not found")
        return order

    @app.get("/orders", response_model=list[OrderOut])
    def list_orders(request: Request, limit: int = 50):
        return request.app.state.repo.list_orders(min(limit, 200))

    return app


app = create_app()
