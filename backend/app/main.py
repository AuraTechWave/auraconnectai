from fastapi import FastAPI
from backend.modules.staff.routes.staff_routes import router as staff_router
from backend.modules.orders.routes.order_routes import router as order_router
from backend.modules.orders.routes.inventory_routes import (
    router as inventory_router
)
from backend.modules.orders.routes.kitchen_routes import (
    router as kitchen_router
)

app = FastAPI()

app.include_router(staff_router)
app.include_router(order_router)
app.include_router(inventory_router)
app.include_router(kitchen_router)


@app.get("/")
def read_root():
    return {"message": "AuraConnect backend is running"}
