from fastapi import APIRouter, Depends
from typing import Optional
from datetime import datetime, timezone, timedelta
from database import db
from auth import get_current_user

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _date_filter(date_from: Optional[str], date_to: Optional[str]):
    """Build a Mongo date filter on created_at (ISO strings)."""
    cond = {}
    if date_from:
        cond["$gte"] = date_from
    if date_to:
        cond["$lte"] = date_to + "T23:59:59"
    return {"created_at": cond} if cond else {}


@router.get("/customer-outstanding/{customer_id}")
async def customer_outstanding(customer_id: str, user=Depends(get_current_user)):
    customer = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if not customer:
        return {"error": "Customer not found"}

    invoices = await db.invoices.find({"customer_id": customer_id}, {"_id": 0}).sort("created_at", -1).to_list(1000)

    # Precompute returns per invoice
    returns_agg = await db.returns.aggregate([
        {"$match": {"customer_id": customer_id}},
        {"$unwind": "$items"},
        {"$group": {"_id": "$invoice_id", "total": {"$sum": "$items.amount"}}}
    ]).to_list(1000)
    returns_map = {r["_id"]: r["total"] for r in returns_agg}

    report_items = []
    total_outstanding = 0
    for inv in invoices:
        alloc_result = await db.payments.aggregate([
            {"$match": {"payment_type": "customer"}},
            {"$unwind": "$allocations"},
            {"$match": {"allocations.reference_id": inv["id"]}},
            {"$group": {"_id": None, "total": {"$sum": "$allocations.amount"}}}
        ]).to_list(1)
        paid = alloc_result[0]["total"] if alloc_result else 0
        returned = returns_map.get(inv["id"], 0)
        balance = inv["total_amount"] - paid - returned

        if balance > 0.01:
            report_items.append({
                "invoice_number": inv["invoice_number"],
                "invoice_id": inv["id"],
                "date": inv["created_at"][:10],
                "total_amount": inv["total_amount"],
                "paid": paid,
                "returned": round(returned, 2),
                "balance": round(balance, 2),
                "status": inv.get("status", "unpaid")
            })
            total_outstanding += balance

    # Opening balance contribution
    opening = float(customer.get("opening_balance", 0))
    total_outstanding += opening

    return {
        "customer_name": customer.get("name", ""),
        "customer_shop": customer.get("shop_name", ""),
        "customer_phone": customer.get("phone", ""),
        "opening_balance": round(opening, 2),
        "items": report_items,
        "total_outstanding": round(total_outstanding, 2),
        "generated_at": datetime.now(timezone.utc).isoformat()
    }


@router.get("/global-outstanding")
async def global_outstanding(user=Depends(get_current_user)):
    customers = await db.customers.find({}, {"_id": 0}).sort("name", 1).to_list(1000)

    inv_totals = await db.invoices.aggregate([
        {"$group": {"_id": "$customer_id", "total": {"$sum": "$total_amount"}}}
    ]).to_list(1000)
    inv_map = {t["_id"]: t["total"] for t in inv_totals}

    pay_totals = await db.payments.aggregate([
        {"$match": {"payment_type": "customer"}},
        {"$group": {"_id": "$entity_id", "total": {"$sum": "$amount"}}}
    ]).to_list(1000)
    pay_map = {t["_id"]: t["total"] for t in pay_totals}

    ret_totals = await db.returns.aggregate([
        {"$unwind": "$items"},
        {"$group": {"_id": "$customer_id", "total": {"$sum": "$items.amount"}}}
    ]).to_list(1000)
    ret_map = {t["_id"]: t["total"] for t in ret_totals}

    report = []
    grand_total = 0
    for c in customers:
        opening = float(c.get("opening_balance", 0))
        outstanding = opening + inv_map.get(c["id"], 0) - pay_map.get(c["id"], 0) - ret_map.get(c["id"], 0)
        if outstanding > 0.01:
            invoices = await db.invoices.find(
                {"customer_id": c["id"], "status": {"$ne": "paid"}},
                {"_id": 0, "invoice_number": 1, "total_amount": 1, "created_at": 1, "status": 1}
            ).to_list(100)
            report.append({
                "customer_id": c["id"],
                "customer_name": c.get("name", ""),
                "customer_shop": c.get("shop_name", ""),
                "opening_balance": round(opening, 2),
                "outstanding": round(outstanding, 2),
                "invoices": [{"invoice_number": i["invoice_number"], "amount": i["total_amount"], "date": i["created_at"][:10], "status": i.get("status", "unpaid")} for i in invoices]
            })
            grand_total += outstanding

    return {
        "items": report,
        "grand_total": round(grand_total, 2),
        "generated_at": datetime.now(timezone.utc).isoformat()
    }


@router.get("/supplier-payable")
async def supplier_payable(user=Depends(get_current_user)):
    suppliers = await db.suppliers.find({}, {"_id": 0}).sort("name", 1).to_list(1000)

    pur_totals = await db.purchases.aggregate([
        {"$group": {"_id": "$supplier_id", "total": {"$sum": "$total_amount"}}}
    ]).to_list(1000)
    pur_map = {t["_id"]: t["total"] for t in pur_totals}

    pay_totals = await db.payments.aggregate([
        {"$match": {"payment_type": "supplier"}},
        {"$group": {"_id": "$entity_id", "total": {"$sum": "$amount"}}}
    ]).to_list(1000)
    pay_map = {t["_id"]: t["total"] for t in pay_totals}

    report = []
    grand_total = 0
    for s in suppliers:
        opening = float(s.get("opening_balance", 0))
        payable = opening + pur_map.get(s["id"], 0) - pay_map.get(s["id"], 0)
        if payable > 0.01:
            purchases = await db.purchases.find(
                {"supplier_id": s["id"]},
                {"_id": 0, "purchase_number": 1, "total_amount": 1, "created_at": 1, "order_number": 1, "supplier_invoice_number": 1}
            ).sort("created_at", -1).to_list(100)
            report.append({
                "supplier_id": s["id"],
                "supplier_name": s.get("name", ""),
                "opening_balance": round(opening, 2),
                "payable": round(payable, 2),
                "purchases": [{"purchase_number": p["purchase_number"], "supplier_invoice_number": p.get("supplier_invoice_number", ""), "amount": p["total_amount"], "date": p["created_at"][:10], "order": p.get("order_number", "")} for p in purchases]
            })
            grand_total += payable

    return {
        "items": report,
        "grand_total": round(grand_total, 2),
        "generated_at": datetime.now(timezone.utc).isoformat()
    }


# ── Payment Reports ──────────────────────────────────────────────────────────

@router.get("/customer-payments")
async def customer_payments_report(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    user=Depends(get_current_user)
):
    query = {"payment_type": "customer"}
    df = _date_filter(date_from, date_to)
    if df:
        query.update(df)

    payments = await db.payments.find(query, {"_id": 0}).sort("created_at", -1).to_list(5000)
    total = sum(p.get("amount", 0) for p in payments)
    items = [
        {
            "id": p["id"],
            "date": p["created_at"][:10],
            "customer_name": p.get("entity_name", ""),
            "amount": p.get("amount", 0),
            "payment_method": p.get("payment_method", ""),
            "cheque_number": p.get("cheque_number", ""),
            "bank_name": p.get("bank_name", ""),
            "cheque_date": p.get("cheque_date", ""),
            "cheques": p.get("cheques", []),
            "notes": p.get("notes", "")
        } for p in payments
    ]
    return {
        "items": items,
        "total": round(total, 2),
        "count": len(items),
        "date_from": date_from,
        "date_to": date_to,
        "generated_at": datetime.now(timezone.utc).isoformat()
    }


@router.get("/supplier-payments")
async def supplier_payments_report(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    user=Depends(get_current_user)
):
    query = {"payment_type": "supplier"}
    df = _date_filter(date_from, date_to)
    if df:
        query.update(df)

    payments = await db.payments.find(query, {"_id": 0}).sort("created_at", -1).to_list(5000)
    total = sum(p.get("amount", 0) for p in payments)
    items = [
        {
            "id": p["id"],
            "date": p["created_at"][:10],
            "supplier_name": p.get("entity_name", ""),
            "amount": p.get("amount", 0),
            "payment_method": p.get("payment_method", ""),
            "cheque_number": p.get("cheque_number", ""),
            "bank_name": p.get("bank_name", ""),
            "cheque_date": p.get("cheque_date", ""),
            "cheques": p.get("cheques", []),
            "notes": p.get("notes", "")
        } for p in payments
    ]
    return {
        "items": items,
        "total": round(total, 2),
        "count": len(items),
        "date_from": date_from,
        "date_to": date_to,
        "generated_at": datetime.now(timezone.utc).isoformat()
    }


# ── Financial Summary ───────────────────────────────────────────────────────

@router.get("/financial-summary")
async def financial_summary(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    user=Depends(get_current_user)
):
    df = _date_filter(date_from, date_to)

    # Sales = invoices total_amount in range
    inv_query = dict(df) if df else {}
    invoices = await db.invoices.find(inv_query, {"_id": 0}).to_list(10000)
    total_sales = sum(i.get("total_amount", 0) for i in invoices)

    # Cost from invoices' items by looking up product cost_price
    total_cost = 0
    customer_ids = set()
    customer_map = {}
    for inv in invoices:
        customer_ids.add(inv.get("customer_id"))
        customer_map[inv.get("customer_id")] = inv.get("customer_name", "")
        for item in inv.get("items", []):
            product = await db.products.find_one({"id": item.get("product_id")}, {"_id": 0, "cost_price": 1})
            if product:
                total_cost += (product.get("cost_price", 0) * item.get("quantity", 0))

    total_profit = total_sales - total_cost

    # Payables: supplier purchases in range
    pur_query = dict(df) if df else {}
    pur_agg = await db.purchases.aggregate([
        {"$match": pur_query} if pur_query else {"$match": {}},
        {"$group": {"_id": None, "total": {"$sum": "$total_amount"}}}
    ]).to_list(1)
    total_purchases = pur_agg[0]["total"] if pur_agg else 0

    # Supplier payments in range (to compute net payable in period)
    sup_pay_query = {"payment_type": "supplier"}
    if df:
        sup_pay_query.update(df)
    sup_pay_agg = await db.payments.aggregate([
        {"$match": sup_pay_query},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
    ]).to_list(1)
    total_sup_paid = sup_pay_agg[0]["total"] if sup_pay_agg else 0
    total_payables = total_purchases - total_sup_paid

    customers = []
    for cid in customer_ids:
        if cid:
            customers.append({"customer_id": cid, "customer_name": customer_map.get(cid, "")})

    return {
        "date_from": date_from,
        "date_to": date_to,
        "total_sales": round(total_sales, 2),
        "total_cost": round(total_cost, 2),
        "total_profit": round(total_profit, 2),
        "total_purchases": round(total_purchases, 2),
        "total_supplier_paid": round(total_sup_paid, 2),
        "total_payables": round(total_payables, 2),
        "customer_count": len(customers),
        "customers": customers,
        "invoice_count": len(invoices),
        "generated_at": datetime.now(timezone.utc).isoformat()
    }
