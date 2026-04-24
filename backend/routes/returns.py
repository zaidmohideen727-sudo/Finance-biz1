from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone
import uuid
from database import db, get_next_sequence
from auth import get_current_user

router = APIRouter(prefix="/api/returns", tags=["returns"])


class ReturnItemInput(BaseModel):
    product_id: str
    product_name: str
    quantity: float
    unit_price: float         # price at which it was sold (for credit amount)
    cost_price: float         # original cost from order/invoice — critical for correct profit when reused
    reason: Optional[str] = ""


class ReturnCreate(BaseModel):
    invoice_id: str
    items: List[ReturnItemInput]
    notes: Optional[str] = ""
    created_at: Optional[str] = None  # backdated returns


async def _add_to_returned_stock(return_id: str, invoice_id: str, customer_id: str, customer_name: str,
                                 item: dict, return_date: str):
    """Create a returned_stock entry (separate per return to preserve cost lineage)."""
    doc = {
        "id": str(uuid.uuid4()),
        "product_id": item["product_id"],
        "product_name": item["product_name"],
        "quantity_available": float(item["quantity"]),
        "quantity_used": 0.0,
        "cost_price": float(item["cost_price"]),
        "unit_price": float(item.get("unit_price", 0)),
        "source": "customer_return",
        "return_id": return_id,
        "invoice_id": invoice_id,
        "customer_id": customer_id,
        "customer_name": customer_name,
        "created_at": return_date,
    }
    await db.returned_stock.insert_one(doc)


@router.get("")
async def list_returns(invoice_id: Optional[str] = None, customer_id: Optional[str] = None, user=Depends(get_current_user)):
    query = {}
    if invoice_id:
        query["invoice_id"] = invoice_id
    if customer_id:
        query["customer_id"] = customer_id
    returns = await db.returns.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return returns


@router.get("/{return_id}")
async def get_return(return_id: str, user=Depends(get_current_user)):
    ret = await db.returns.find_one({"id": return_id}, {"_id": 0})
    if not ret:
        raise HTTPException(status_code=404, detail="Return not found")
    return ret


@router.post("")
async def create_return(data: ReturnCreate, user=Depends(get_current_user)):
    invoice = await db.invoices.find_one({"id": data.invoice_id}, {"_id": 0})
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    # Validate return quantities don't exceed invoice quantities (minus prior returns)
    inv_qty = {}
    for item in invoice.get("items", []):
        inv_qty[item["product_id"]] = inv_qty.get(item["product_id"], 0) + float(item["quantity"])

    prior_returns = await db.returns.find({"invoice_id": data.invoice_id}, {"_id": 0}).to_list(1000)
    prior_qty = {}
    for r in prior_returns:
        for ri in r.get("items", []):
            prior_qty[ri["product_id"]] = prior_qty.get(ri["product_id"], 0) + float(ri["quantity"])

    for item in data.items:
        available = inv_qty.get(item.product_id, 0) - prior_qty.get(item.product_id, 0)
        if item.quantity > available + 0.0001:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot return {item.quantity} of '{item.product_name}' — only {available} available on this invoice"
            )

    seq = await get_next_sequence("returns")
    return_number = f"RET-{seq:04d}"
    return_id = str(uuid.uuid4())
    created_at = data.created_at or datetime.now(timezone.utc).isoformat()

    items = []
    total = 0
    for it in data.items:
        amount = round(it.quantity * it.unit_price, 2)
        item_doc = {
            "id": str(uuid.uuid4()),
            "product_id": it.product_id,
            "product_name": it.product_name,
            "quantity": it.quantity,
            "unit_price": it.unit_price,
            "cost_price": it.cost_price,
            "amount": amount,
            "reason": it.reason or "",
        }
        items.append(item_doc)
        total += amount

    doc = {
        "id": return_id,
        "return_number": return_number,
        "invoice_id": data.invoice_id,
        "invoice_number": invoice.get("invoice_number", ""),
        "customer_id": invoice.get("customer_id", ""),
        "customer_name": invoice.get("customer_name", ""),
        "items": items,
        "total_amount": round(total, 2),
        "notes": data.notes or "",
        "created_at": created_at,
    }
    await db.returns.insert_one(doc)

    # Create returned_stock entries (one per returned item)
    for it in items:
        await _add_to_returned_stock(
            return_id, data.invoice_id,
            invoice.get("customer_id", ""), invoice.get("customer_name", ""),
            it, created_at
        )

    doc.pop("_id", None)
    return doc


@router.delete("/{return_id}")
async def delete_return(return_id: str, user=Depends(get_current_user)):
    ret = await db.returns.find_one({"id": return_id}, {"_id": 0})
    if not ret:
        raise HTTPException(status_code=404, detail="Return not found")

    # Delete related returned_stock — but ONLY if unused. If stock was consumed
    # by new orders, block deletion to preserve integrity.
    stocks = await db.returned_stock.find({"return_id": return_id}, {"_id": 0}).to_list(100)
    for s in stocks:
        if float(s.get("quantity_used", 0)) > 0:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot delete return — some returned stock already used in a new order (product: {s['product_name']})"
            )

    await db.returned_stock.delete_many({"return_id": return_id})
    await db.returns.delete_one({"id": return_id})
    return {"message": "Return deleted and stock reversed"}
