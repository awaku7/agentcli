"""UCP モックサーバー — Phase 3 AP2 対応（完全自律決済）。

UCP Business + Credential Provider シミュレーション。
"""

import uuid
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="UCP Mock Merchant", version="0.5.0")

# ---------------------------------------------------------------------------
# In-memory store
# ---------------------------------------------------------------------------
_carts: dict[str, dict] = {}
_checkouts: dict[str, dict] = {}
_orders: dict[str, dict] = {}
_order_seq = 0
_identity_links: dict[str, dict] = {}
_ap2_mandates: dict[str, dict] = {}

# ---------------------------------------------------------------------------
# Sample products
# ---------------------------------------------------------------------------
PRODUCTS = [
    {
        "id": "item_001",
        "title": "Monos Carry-On Pro",
        "price": 26550,
        "currency": "USD",
        "description": "Premium carry-on luggage",
        "category": "luggage",
    },
    {
        "id": "item_002",
        "title": "Away Bigger Carry-On",
        "price": 29500,
        "currency": "USD",
        "description": "Polycarbonate carry-on",
        "category": "luggage",
    },
    {
        "id": "item_003",
        "title": "Away Large Suitcase",
        "price": 34500,
        "currency": "USD",
        "description": "Checked luggage 75L",
        "category": "luggage",
    },
    {
        "id": "item_004",
        "title": "Peak Design Travel Backpack 45L",
        "price": 29995,
        "currency": "USD",
        "description": "Travel backpack",
        "category": "bags",
    },
    {
        "id": "item_005",
        "title": "Apple AirTag (4-pack)",
        "price": 9900,
        "currency": "USD",
        "description": "Item tracker",
        "category": "accessories",
    },
    # 新規商品
    {
        "id": "item_010",
        "title": "Organic Coffee Beans - Medium Roast",
        "price": 1850,
        "currency": "USD",
        "description": "Fair trade organic coffee 12oz",
        "category": "food",
    },
    {
        "id": "item_011",
        "title": "Matcha Green Tea Powder",
        "price": 2800,
        "currency": "USD",
        "description": "Ceremonial grade matcha 100g",
        "category": "food",
    },
    {
        "id": "item_012",
        "title": "Dark Chocolate Bar 72%",
        "price": 450,
        "currency": "USD",
        "description": "Single origin dark chocolate",
        "category": "food",
    },
    {
        "id": "item_020",
        "title": "Bamboo Cutting Board",
        "price": 2495,
        "currency": "USD",
        "description": "Large bamboo cutting board",
        "category": "kitchen",
    },
    {
        "id": "item_021",
        "title": "Stainless Steel Water Bottle 1L",
        "price": 3500,
        "currency": "USD",
        "description": "Double wall vacuum insulated",
        "category": "kitchen",
    },
    {
        "id": "item_030",
        "title": "Merino Wool T-Shirt",
        "price": 6500,
        "currency": "USD",
        "description": "Lightweight merino wool crew neck",
        "category": "clothing",
    },
    {
        "id": "item_031",
        "title": "Cashmere Beanie",
        "price": 4500,
        "currency": "USD",
        "description": "Premium cashmere knit beanie",
        "category": "clothing",
    },
    {
        "id": "item_040",
        "title": "Yoga Mat Premium",
        "price": 6800,
        "currency": "USD",
        "description": "Non-slip eco-friendly yoga mat 6mm",
        "category": "sports",
    },
    {
        "id": "item_041",
        "title": "Resistance Bands Set",
        "price": 2200,
        "currency": "USD",
        "description": "Set of 5 resistance bands",
        "category": "sports",
    },
    {
        "id": "item_050",
        "title": "LED Desk Lamp",
        "price": 4200,
        "currency": "USD",
        "description": "Adjustable LED desk lamp with USB",
        "category": "home",
    },
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
                    "spec": "",
                    "schema": "",
                }
            ]
        },
        "capabilities": {
            "dev.ucp.shopping.catalog_search": [
                {"version": "2026-04-08", "spec": "", "schema": ""}
            ],
            "dev.ucp.shopping.catalog_lookup": [
                {"version": "2026-04-08", "spec": "", "schema": ""}
            ],
            "dev.ucp.shopping.cart": [
                {"version": "2026-04-08", "spec": "", "schema": ""}
            ],
            "dev.ucp.shopping.checkout": [
                {"version": "2026-04-08", "spec": "", "schema": ""}
            ],
            "dev.ucp.shopping.order": [
                {"version": "2026-04-08", "spec": "", "schema": ""}
            ],
        },
        "payment_handlers": {
            "com.google.pay": [
                {
                    "id": "gpay",
                    "version": "2026-01-11",
                    "spec": "",
                    "config_schema": "",
                    "instrument_schemas": [],
                }
            ]
        },
    }
}


@app.get("/.well-known/ucp")
async def well_known():
    return PROFILE


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------
@app.post("/search")
async def search_catalog(request: Request):
    body = await request.json()
    query = body.get("query", "").lower()
    results = [
        p
        for p in PRODUCTS
        if query in p["title"].lower() or query in p["description"].lower()
    ]
    return JSONResponse(content={"results": results, "total": len(results)})


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
    enriched, total = [], 0
    for item in line_items:
        pid, qty = item.get("item_id", ""), item.get("quantity", 1)
        product = next((p for p in PRODUCTS if p["id"] == pid), None)
        if product:
            enriched.append(
                {
                    "item_id": pid,
                    "title": product["title"],
                    "quantity": qty,
                    "unit_price": product["price"],
                }
            )
            total += product["price"] * qty
    _carts[cart_id] = {
        "id": cart_id,
        "line_items": enriched,
        "currency": body.get("currency", "USD"),
    }
    return JSONResponse(
        content={
            "id": cart_id,
            "line_items": enriched,
            "currency": body.get("currency", "USD"),
            "totals": {"total": total, "subtotal": total},
            "status": "active",
        },
        status_code=201,
    )


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
    enriched, total = [], 0
    for item in line_items:
        pid, qty = item.get("item_id", ""), item.get("quantity", 1)
        product = next((p for p in PRODUCTS if p["id"] == pid), None)
        if product:
            enriched.append(
                {
                    "item_id": pid,
                    "title": product["title"],
                    "quantity": qty,
                    "unit_price": product["price"],
                }
            )
            total += product["price"] * qty
    cart["line_items"] = enriched
    return {
        "id": cart_id,
        "line_items": enriched,
        "currency": cart["currency"],
        "totals": {"total": total},
    }


# ---------------------------------------------------------------------------
# Checkout with continue_url + AP2 token support
# ---------------------------------------------------------------------------
@app.post("/checkout-sessions")
async def create_checkout(request: Request):
    body = await request.json()
    checkout_id = "chk_" + str(uuid.uuid4())[:8]
    cart_id = body.get("cart_id", "")
    line_items = body.get("line_items", [])
    if cart_id and cart_id in _carts:
        line_items = _carts[cart_id].get("line_items", [])
    total = sum(
        item.get("unit_price", 0) * item.get("quantity", 1) for item in line_items
    )
    checkout_data = {
        "id": checkout_id,
        "line_items": line_items,
        "status": "ready_for_complete",
        "currency": body.get("currency", "USD"),
        "totals": {"total": total, "subtotal": total},
        "messages": [],
        "payment": {"handlers": [{"id": "gpay", "name": "Google Pay", "type": "card"}]},
        "buyer": body.get("buyer"),
    }
    # Handle fulfillment (shipping)
    fulfillment = body.get("fulfillment")
    if fulfillment:
        checkout_data["fulfillment"] = fulfillment
    # Handle vendor extensions
    extensions = body.get("extensions")
    if extensions:
        checkout_data["extensions"] = extensions
    _checkouts[checkout_id] = checkout_data
    return JSONResponse(content=_checkouts[checkout_id], status_code=201)


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

    # Check for AP2 token
    body = await request.json()
    ap2_token = body.get("ap2_token", "")

    if ap2_token:
        # AP2 autonomous payment flow
        # In production, the merchant would verify the token with CP
        # For mock, we accept any signed token
        _orders_seq_inner = __import__("uuid").uuid4()
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
        checkout["order_id"] = order_id
        return JSONResponse(
            content={
                "id": order_id,
                "checkout_id": checkout_id,
                "status": "completed",
                "order": order,
            }
        )
    elif checkout.get("status") == "completed":
        order = _orders.get(checkout.get("order_id", ""))
        return JSONResponse(
            content={
                "id": checkout.get("order_id"),
                "checkout_id": checkout_id,
                "status": "completed",
                "order": order,
            }
        )
    else:
        # continue_url flow
        continue_url = f"http://localhost:8080/pay/{checkout_id}"
        checkout["status"] = "requires_escalation"
        checkout["continue_url"] = continue_url
        checkout["messages"] = [
            {
                "severity": "requires_buyer_review",
                "code": "payment_required",
                "message": "Buyer must complete payment in browser",
                "detail": "",
            }
        ]
        return JSONResponse(content=checkout, status_code=200)


@app.get("/pay/{checkout_id}")
async def payment_page(checkout_id: str):
    checkout = _checkouts.get(checkout_id)
    if not checkout:
        return HTML_RESPONSE.format(body="<h1>Checkout not found</h1>")
    total = checkout.get("totals", {}).get("total", 0)
    items_html = "".join(
        f"<li>{item.get('title', 'Item')} x {item.get('quantity', 1)}</li>"
        for item in checkout.get("line_items", [])
    )
    return HTML_RESPONSE.format(
        body=f"<h1>Mock Payment Page</h1><p>Total: ${total/100:.2f}</p><ul>{items_html}</ul><form action='/pay/{checkout_id}' method='post'><button style='padding:12px 24px;font-size:16px;background:#1a73e8;color:white;border:none;border-radius:4px;cursor:pointer'>Pay</button></form>"
    )


@app.post("/pay/{checkout_id}")
async def payment_complete(checkout_id: str):
    checkout = _checkouts.get(checkout_id)
    if not checkout:
        return HTML_RESPONSE.format(body="<h1>Checkout not found</h1>")
    global _order_seq
    _order_seq += 1
    order_id = "ord_" + str(_order_seq).zfill(6)
    _orders[order_id] = {
        "id": order_id,
        "checkout_id": checkout_id,
        "status": "completed",
        "line_items": checkout.get("line_items", []),
        "currency": checkout.get("currency", "USD"),
        "totals": checkout.get("totals", {}),
    }
    checkout["status"] = "completed"
    checkout["order_id"] = order_id
    return HTML_RESPONSE.format(
        body=f"<h1>Payment Successful!</h1><p>Order ID: {order_id}</p>"
    )


HTML_RESPONSE = '<html><body style="font-family:sans-serif;max-width:600px;margin:50px auto">{body}</body></html>'


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
# Identity Linking
# ---------------------------------------------------------------------------
@app.post("/identity-link")
async def identity_link(request: Request):
    body = await request.json()
    redirect_uri = body.get("redirect_uri", "http://localhost:3000/callback")
    link_id = "link_" + str(uuid.uuid4())[:8]
    auth_url = f"http://localhost:8080/oauth/authorize?link_id={link_id}&redirect_uri={redirect_uri}"
    _identity_links[link_id] = {
        "id": link_id,
        "status": "pending",
        "redirect_uri": redirect_uri,
        "authorization_url": auth_url,
    }
    return JSONResponse(
        content={"id": link_id, "status": "pending", "authorization_url": auth_url},
        status_code=201,
    )


@app.get("/oauth/authorize")
async def oauth_authorize(request: Request):
    link_id = request.query_params.get("link_id", "")
    if link_id not in _identity_links:
        return HTML_RESPONSE.format(body="<h1>Link not found</h1>")
    return HTML_RESPONSE.format(
        body=f"<h1>OAuth Authorization</h1><p>Link ID: {link_id}</p><form action='/oauth/authorize/{link_id}' method='post'><button>Authorize</button></form>"
    )


@app.post("/oauth/authorize/{link_id}")
async def oauth_authorize_confirm(link_id: str):
    if link_id not in _identity_links:
        return HTML_RESPONSE.format(body="<h1>Link not found</h1>")
    _identity_links[link_id]["status"] = "linked"
    return HTML_RESPONSE.format(body="<h1>Authorization Successful!</h1>")


@app.post("/identity-link-status")
async def identity_link_status(request: Request):
    body = await request.json()
    link_id = body.get("link_id", "")
    link = _identity_links.get(link_id)
    if not link:
        return JSONResponse(content={"error": "link not found"}, status_code=404)
    return JSONResponse(
        content={"id": link_id, "status": link.get("status", "pending")}
    )


# ---------------------------------------------------------------------------
# AP2 Mandate Authorization (Trusted Surface simulation)
# ---------------------------------------------------------------------------
@app.get("/ap2/authorize/{mandate_id}")
async def ap2_authorize_page(mandate_id: str):
    """User authorizes an AP2 payment mandate via browser."""
    mandate = _ap2_mandates.get(mandate_id)
    if not mandate:
        return HTML_RESPONSE.format(body="<h1>Mandate not found</h1>")
    return HTML_RESPONSE.format(
        body=f"<h1>AP2 Payment Mandate Authorization</h1>"
        f"<p>Merchant: {mandate.get('merchant_name', 'Unknown')}</p>"
        f"<p>Max Amount: ${mandate.get('max_amount', 0)/100:.2f}</p>"
        f"<form action='/ap2/authorize/{mandate_id}' method='post'>"
        f"<button style='padding:12px 24px;font-size:16px;background:#1a73e8;color:white;border:none;border-radius:4px;cursor:pointer'>"
        f"Authorize Mandate</button></form>"
    )


@app.post("/ap2/authorize/{mandate_id}")
async def ap2_authorize_confirm(mandate_id: str):
    """User confirms the AP2 mandate in browser."""
    mandate = _ap2_mandates.get(mandate_id)
    if not mandate:
        return HTML_RESPONSE.format(body="<h1>Mandate not found</h1>")
    mandate["status"] = "active"
    return HTML_RESPONSE.format(
        body=f"<h1>Mandate Authorized!</h1>"
        f"<p>Mandate ID: {mandate_id}</p>"
        f"<p>The agent can now make autonomous purchases up to ${mandate.get('max_amount', 0)/100:.2f}.</p>"
        f"<p>You can close this window.</p>"
    )


@app.post("/ap2/mandate-status")
async def ap2_mandate_status(request: Request):
    """Check AP2 mandate authorization status."""
    body = await request.json()
    mandate_id = body.get("mandate_id", "")
    mandate = _ap2_mandates.get(mandate_id)
    if not mandate:
        return JSONResponse(content={"error": "mandate not found"}, status_code=404)
    return JSONResponse(
        content={
            "id": mandate_id,
            "status": mandate.get("status", "pending"),
            "merchant_name": mandate.get("merchant_name"),
            "max_amount": mandate.get("max_amount"),
        }
    )


@app.post("/ap2/register-mandate")
async def ap2_register_mandate(request: Request):
    """Register a mandate created by the agent (simulates CP storage)."""
    body = await request.json()
    mandate_id = body.get("mandate_id", "")
    if not mandate_id:
        mandate_id = "mnt_" + str(uuid.uuid4())[:8]
    _ap2_mandates[mandate_id] = {
        "id": mandate_id,
        "status": "pending",
        "merchant_name": body.get("merchant_name", ""),
        "max_amount": body.get("max_amount", 0),
        "currency": body.get("currency", "USD"),
    }
    return JSONResponse(
        content={"id": mandate_id, "status": "pending"}, status_code=201
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 60)
    print("UCP Mock Merchant Server v0.6.0 (Phase6 Extensions)")
    print("Profile: http://localhost:8080/.well-known/ucp")
    print("AP2:     /ap2/authorize/{id}, /ap2/mandate-status")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")
