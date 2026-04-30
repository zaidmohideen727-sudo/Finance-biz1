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
    # Phase 7: where does the stock go?
    # - "warehouse": add to returned_stock pool (default, existing behavior)
    # - "supplier":  reduce linked supplier purchase value & supplier payable
    destination: Optional[str] = "warehouse"
    supplier_id: Optional[str] = ""
    supplier_name: Optional[str] = ""
    purchase_id: Optional[str] = ""   # specific purchase to reduce (optional)


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
        "credit_note_number": f"CN-{seq:04d}",
        "invoice_id": data.invoice_id,
        "invoice_number": invoice.get("invoice_number", ""),
        "customer_id": invoice.get("customer_id", ""),
        "customer_name": invoice.get("customer_name", ""),
        "items": items,
        "total_amount": round(total, 2),
        "destination": data.destination or "warehouse",
        "supplier_id": data.supplier_id or "",
        "supplier_name": data.supplier_name or "",
        "purchase_id": data.purchase_id or "",
        "notes": data.notes or "",
        "created_at": created_at,
    }
    await db.returns.insert_one(doc)

    if doc["destination"] == "supplier":
        # Reduce supplier payable by subtracting the returned value from the
        # linked purchase. We append a negative "supplier_return" adjustment to
        # the purchase so total_amount decreases. Audit trail is preserved.
        target_purchase = None
        if data.purchase_id:
            target_purchase = await db.purchases.find_one({"id": data.purchase_id}, {"_id": 0})
        elif invoice.get("linked_purchase_id"):
            target_purchase = await db.purchases.find_one({"id": invoice["linked_purchase_id"]}, {"_id": 0})
        elif data.supplier_id:
            # Heuristic: pick the most recent unadjusted purchase from that supplier
            target_purchase = await db.purchases.find_one(
                {"supplier_id": data.supplier_id},
                {"_id": 0},
                sort=[("created_at", -1)],
            )
        if target_purchase:
            # Each return item reduces the cost side of the purchase
            adjustment_total = 0.0
            adjustments = list(target_purchase.get("supplier_return_adjustments", []))
            for it in items:
                cost = float(it.get("cost_price", 0)) or 0
                adj_amount = round(float(it["quantity"]) * cost, 2)
                adjustment_total += adj_amount
                adjustments.append({
                    "id": str(uuid.uuid4()),
                    "return_id": return_id,
                    "return_number": return_number,
                    "product_id": it["product_id"],
                    "product_name": it["product_name"],
                    "quantity": float(it["quantity"]),
                    "cost_price": cost,
                    "amount": adj_amount,
                    "adjusted_at": created_at,
                })
            new_total = max(0.0, round(float(target_purchase.get("total_amount", 0)) - adjustment_total, 2))
            await db.purchases.update_one(
                {"id": target_purchase["id"]},
                {"$set": {
                    "supplier_return_adjustments": adjustments,
                    "total_amount": new_total,
                }}
            )
            doc["adjusted_purchase_id"] = target_purchase["id"]
            doc["adjusted_purchase_number"] = target_purchase.get("purchase_number")
            doc["adjusted_amount"] = adjustment_total
            await db.returns.update_one(
                {"id": return_id},
                {"$set": {
                    "adjusted_purchase_id": target_purchase["id"],
                    "adjusted_purchase_number": target_purchase.get("purchase_number"),
                    "adjusted_amount": adjustment_total,
                }}
            )
    else:
        # Default: add to warehouse stock pool
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

    if ret.get("destination") == "supplier":
        # Reverse purchase adjustment
        pur_id = ret.get("adjusted_purchase_id")
        if pur_id:
            purchase = await db.purchases.find_one({"id": pur_id}, {"_id": 0})
            if purchase:
                kept = [a for a in purchase.get("supplier_return_adjustments", []) if a.get("return_id") != return_id]
                removed_total = sum(
                    a.get("amount", 0) for a in purchase.get("supplier_return_adjustments", [])
                    if a.get("return_id") == return_id
                )
                new_total = round(float(purchase.get("total_amount", 0)) + float(removed_total), 2)
                await db.purchases.update_one(
                    {"id": pur_id},
                    {"$set": {
                        "supplier_return_adjustments": kept,
                        "total_amount": new_total,
                    }}
                )
        await db.returns.delete_one({"id": return_id})
        return {"message": "Supplier return reversed"}

    # Warehouse return — preserve integrity check
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
