"""UCP モックサーバー — Phase 1 Core テスト用。

UCP Business の最小限のシミュレーションを行う。
FastAPI で起動し、/.well-known/ucp での Profile 公開と、
カタログ・カート・チェックアウトの各APIを模擬応答する。
"""

import json
import uuid
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="UCP Mock Merchant", version="0.1.0")

# ---------------------------------------------------------------------------
# In-memory store
# ---------------------------------------------------------------------------
_carts: dict[str, dict] = {}
_checkouts: dict[str, dict] = {}
_orders: dict[str, dict] = {}
_order_seq = 0

# ---------------------------------------------------------------------------
# Sample products
# ---------------------------------------------------------------------------
PRODUCTS = [
    {"id": "item_001", "title": "Monos Carry-On Pro", "price": 26550, "currency": "USD", "description": "Premium carry-on luggage"},
    {"id": "item_002", "title": "Away Bigger Carry-On", "price": 29500, "currency": "USD", "description": "Polycarbonate carry-on"},
    {"id": "item_003", "title": "Away Large Suitcase", "price": 34500, "currency": "USD", "description": "Checked luggage 75L"},
    {"id": "item_004", "title": "Peak Design Travel Backpack 45L", "price": 29995, "currency": "USD", "description": "Travel backpack"},
    {"id": "item_005", "title": "Apple AirTag (4-pack)", "price": 9900, "currency": "USD", "description": "Item tracker"},
]

# ---------------------------------------------------------------------------
# Discovery profile
# ---------------------------------------------------------------------------
PROFILE = {
    "ucp": {
        "version": "2026-04-08",
        "services": {
            "dev.ucp.shopping": [
                {
                    "version": "2026-04-08",
                    "transport": "rest",
                    "endpoint": "http://localhost:8080",
                    "spec": "https://ucp.dev/2026-04-08/specification/overview",
                    "schema": "https://ucp.dev/2026-04-08/schemas/shopping/checkout.json",
                }
            ]
        },
        "capabilities": {
            "dev.ucp.shopping.catalog_search": [
                {"version": "2026-04-08", "spec": "https://ucp.dev/2026-04-08/specification/catalog", "schema": ""}
            ],
            "dev.ucp.shopping.catalog_lookup": [
                {"version": "2026-04-08", "spec": "https://ucp.dev/2026-04-08/specification/catalog", "schema": ""}
            ],
            "dev.ucp.shopping.cart": [
                {"version": "2026-04-08", "spec": "https://ucp.dev/2026-04-08/specification/cart", "schema": ""}
            ],
            "dev.ucp.shopping.checkout": [
                {"version": "2026-04-08", "spec": "https://ucp.dev/2026-04-08/specification/checkout", "schema": ""}
            ],
            "dev.ucp.shopping.order": [
                {"version": "2026-04-08", "spec": "https://ucp.dev/2026-04-08/specification/order", "schema": ""}
            ],
        },
        "payment_handlers": {},
    }
}


@app.get("/.well-known/ucp")
async def well_known():
    return PROFILE


# ---------------------------------------------------------------------------
# Catalog Search
# ---------------------------------------------------------------------------
@app.post("/search")
async def search_catalog(request: Request):
    body = await request.json()
    query = body.get("query", "").lower()
    results = [p for p in PRODUCTS if query in p["title"].lower() or query in p["description"].lower()]
    return JSONResponse(content={"results": results, "total": len(results)})


# ---------------------------------------------------------------------------
# Catalog Lookup
# ---------------------------------------------------------------------------
@app.post("/lookup-catalog")
async def lookup_catalog(request: Request):
    body = await request.json()
    item_ids = body.get("item_ids", [])
    results = [p for p in PRODUCTS if p["id"] in item_ids]
    return JSONResponse(content={"results": results})


# ---------------------------------------------------------------------------
# Cart
# ---------------------------------------------------------------------------
@app.post("/carts")
async def create_cart(request: Request):
    body = await request.json()
    cart_id = "cart_" + str(uuid.uuid4())[:8]
    line_items = body.get("line_items", [])
    # Enrich line items with product data
    enriched = []
    total = 0
    for item in line_items:
        pid = item.get("item_id", "")
        qty = item.get("quantity", 1)
        product = next((p for p in PRODUCTS if p["id"] == pid), None)
        if product:
            enriched.append({"item_id": pid, "title": product["title"], "quantity": qty, "unit_price": product["price"]})
            total += product["price"] * qty
    _carts[cart_id] = {"id": cart_id, "line_items": enriched, "currency": body.get("currency", "USD")}
    return JSONResponse(content={
        "id": cart_id,
        "line_items": enriched,
        "currency": body.get("currency", "USD"),
        "totals": {"total": total, "subtotal": total},
        "status": "active",
    }, status_code=201)


@app.get("/carts/{cart_id}")
async def get_cart(cart_id: str):
    cart = _carts.get(cart_id)
    if not cart:
        return JSONResponse(content={"error": "cart not found"}, status_code=404)
    return cart


@app.patch("/carts/{cart_id}")
async def update_cart(cart_id: str, request: Request):
    cart = _carts.get(cart_id)
    if not cart:
        return JSONResponse(content={"error": "cart not found"}, status_code=404)
    body = await request.json()
    line_items = body.get("line_items", [])
    enriched = []
    total = 0
    for item in line_items:
        pid = item.get("item_id", "")
        qty = item.get("quantity", 1)
        product = next((p for p in PRODUCTS if p["id"] == pid), None)
        if product:
            enriched.append({"item_id": pid, "title": product["title"], "quantity": qty, "unit_price": product["price"]})
            total += product["price"] * qty
    cart["line_items"] = enriched
    return {"id": cart_id, "line_items": enriched, "currency": cart["currency"], "totals": {"total": total}}


# ---------------------------------------------------------------------------
# Checkout
# ---------------------------------------------------------------------------
@app.post("/checkout-sessions")
async def create_checkout(request: Request):
    body = await request.json()
    checkout_id = "chk_" + str(uuid.uuid4())[:8]
    cart_id = body.get("cart_id", "")
    
    line_items = body.get("line_items", [])
    if cart_id and cart_id in _carts:
        line_items = _carts[cart_id].get("line_items", [])
    
    total = sum(item.get("unit_price", 0) * item.get("quantity", 1) for item in line_items)
    
    checkout = {
        "id": checkout_id,
        "line_items": line_items,
        "status": "ready_for_complete",
        "currency": body.get("currency", "USD"),
        "totals": {"total": total, "subtotal": total},
        "messages": [],
    }
    _checkouts[checkout_id] = checkout
    return JSONResponse(content=checkout, status_code=201)


@app.get("/checkout-sessions/{checkout_id}")
async def get_checkout(checkout_id: str):
    checkout = _checkouts.get(checkout_id)
    if not checkout:
        return JSONResponse(content={"error": "checkout not found"}, status_code=404)
    return checkout


@app.patch("/checkout-sessions/{checkout_id}")
async def update_checkout(checkout_id: str, request: Request):
    checkout = _checkouts.get(checkout_id)
    if not checkout:
        return JSONResponse(content={"error": "checkout not found"}, status_code=404)
    body = await request.json()
    if "line_items" in body:
        checkout["line_items"] = body["line_items"]
    return checkout


@app.post("/checkout-sessions/{checkout_id}/complete")
async def complete_checkout(checkout_id: str, request: Request):
    checkout = _checkouts.get(checkout_id)
    if not checkout:
        return JSONResponse(content={"error": "checkout not found"}, status_code=404)
    
    global _order_seq
    _order_seq += 1
    order_id = "ord_" + str(_order_seq).zfill(6)
    
    order = {
        "id": order_id,
        "checkout_id": checkout_id,
        "status": "completed",
        "line_items": checkout.get("line_items", []),
        "currency": checkout.get("currency", "USD"),
        "totals": checkout.get("totals", {}),
    }
    _orders[order_id] = order
    checkout["status"] = "completed"
    
    return JSONResponse(content={
        "id": order_id,
        "checkout_id": checkout_id,
        "status": "completed",
        "order": order,
    })


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------
@app.post("/list-orders")
async def list_orders():
    return JSONResponse(content={"orders": list(_orders.values())})


@app.post("/get-order")
async def get_order(request: Request):
    body = await request.json()
    order_id = body.get("order_id", "")
    order = _orders.get(order_id)
    if not order:
        return JSONResponse(content={"error": "order not found"}, status_code=404)
    return order


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 60)
    print("UCP Mock Merchant Server starting on http://localhost:8080")
    print("Profile: http://localhost:8080/.well-known/ucp")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")
