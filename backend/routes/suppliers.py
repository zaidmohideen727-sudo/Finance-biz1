from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import uuid
from database import db
from auth import get_current_user

router = APIRouter(prefix="/api/suppliers", tags=["suppliers"])


class SupplierCreate(BaseModel):
    name: str
    phone: Optional[str] = ""
    address: Optional[str] = ""
    is_primary: Optional[bool] = False
    opening_balance: Optional[float] = 0


class SupplierUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    is_primary: Optional[bool] = None
    opening_balance: Optional[float] = None


@router.get("")
async def list_suppliers(search: Optional[str] = None, user=Depends(get_current_user)):
    query = {}
    if search:
        query = {"$or": [
            {"name": {"$regex": search, "$options": "i"}},
            {"phone": {"$regex": search, "$options": "i"}}
        ]}
    suppliers = await db.suppliers.find(query, {"_id": 0}).sort("name", 1).to_list(1000)

    pur_totals = await db.purchases.aggregate([
        {"$group": {"_id": "$supplier_id", "total": {"$sum": "$total_amount"}}}
    ]).to_list(1000)
    pur_map = {t["_id"]: t["total"] for t in pur_totals}

    pay_totals = await db.payments.aggregate([
        {"$match": {"payment_type": "supplier"}},
        {"$group": {"_id": "$entity_id", "total": {"$sum": "$amount"}}}
    ]).to_list(1000)
    pay_map = {t["_id"]: t["total"] for t in pay_totals}

    for s in suppliers:
        opening = float(s.get("opening_balance", 0))
        s["payable"] = round(opening + pur_map.get(s["id"], 0) - pay_map.get(s["id"], 0), 2)

    return suppliers


@router.get("/{supplier_id}")
async def get_supplier(supplier_id: str, user=Depends(get_current_user)):
    supplier = await db.suppliers.find_one({"id": supplier_id}, {"_id": 0})
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    pur_pipeline = [
        {"$match": {"supplier_id": supplier_id}},
        {"$group": {"_id": None, "total": {"$sum": "$total_amount"}}}
    ]
    pur_result = await db.purchases.aggregate(pur_pipeline).to_list(1)
    total_purchased = pur_result[0]["total"] if pur_result else 0

    pay_pipeline = [
        {"$match": {"entity_id": supplier_id, "payment_type": "supplier"}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
    ]
    pay_result = await db.payments.aggregate(pay_pipeline).to_list(1)
    total_paid = pay_result[0]["total"] if pay_result else 0

    supplier["opening_balance"] = round(float(supplier.get("opening_balance", 0)), 2)
    supplier["payable"] = round(supplier["opening_balance"] + total_purchased - total_paid, 2)
    supplier["purchases"] = await db.purchases.find({"supplier_id": supplier_id}, {"_id": 0}).sort("created_at", -1).to_list(50)
    supplier["payments"] = await db.payments.find({"entity_id": supplier_id, "payment_type": "supplier"}, {"_id": 0}).sort("created_at", -1).to_list(50)

    # Analytics: fast moving items
    product_counts = {}
    for pur in supplier["purchases"]:
        for item in pur.get("items", []):
            pname = item.get("product_name", "Unknown")
            product_counts[pname] = product_counts.get(pname, 0) + item.get("quantity", 0)
    fast_moving = sorted(product_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    supplier["fast_moving_items"] = [{"product": p, "quantity": q} for p, q in fast_moving]

    payments = supplier["payments"]
    supplier["last_payment"] = payments[0] if payments else None

    return supplier


@router.post("")
async def create_supplier(data: SupplierCreate, user=Depends(get_current_user)):
    doc = {
        "id": str(uuid.uuid4()),
        "name": data.name,
        "phone": data.phone or "",
        "address": data.address or "",
        "is_primary": data.is_primary or False,
        "opening_balance": float(data.opening_balance or 0),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.suppliers.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.put("/{supplier_id}")
async def update_supplier(supplier_id: str, data: SupplierUpdate, user=Depends(get_current_user)):
    update = {k: v for k, v in data.model_dump().items() if v is not None}
    if not update:
        raise HTTPException(status_code=400, detail="No fields to update")
    await db.suppliers.update_one({"id": supplier_id}, {"$set": update})
    supplier = await db.suppliers.find_one({"id": supplier_id}, {"_id": 0})
    return supplier


@router.delete("/{supplier_id}")
async def delete_supplier(supplier_id: str, user=Depends(get_current_user)):
    result = await db.suppliers.delete_one({"id": supplier_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return {"message": "Supplier deleted"}
