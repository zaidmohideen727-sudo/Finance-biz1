import { useState, useEffect, useCallback } from "react";
import API from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { SearchableSelect } from "@/components/SearchableSelect";
import { toast } from "sonner";
import { History, Plus, X } from "lucide-react";

const fmt = (n) => new Intl.NumberFormat("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n || 0);

export default function MigrationPage() {
  const [tab, setTab] = useState("invoice");
  const [customers, setCustomers] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [products, setProducts] = useState([]);
  const [invoices, setInvoices] = useState([]);

  // Historical invoice
  const [invForm, setInvForm] = useState({ customer_id: "", customer_name: "", customer_shop_name: "", invoice_number: "", created_at: "", items: [], notes: "" });

  // Historical purchase
  const [purForm, setPurForm] = useState({ supplier_id: "", supplier_name: "", supplier_invoice_number: "", purchase_number: "", created_at: "", items: [], notes: "" });

  // Historical payment
  const [payForm, setPayForm] = useState({ payment_type: "customer", entity_id: "", entity_name: "", amount: "", payment_method: "cash", created_at: "", reference_id: "", notes: "" });

  // Opening balance
  const [obForm, setObForm] = useState({ entity_type: "customer", entity_id: "", entity_name: "", opening_balance: 0 });

  const load = useCallback(async () => {
    try {
      const [c, s, p, i] = await Promise.all([
        API.get("/customers"), API.get("/suppliers"), API.get("/products"), API.get("/invoices")
      ]);
      setCustomers(c.data); setSuppliers(s.data); setProducts(p.data); setInvoices(i.data);
    } catch (err) { console.error(err); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const customerOptions = customers.map(c => ({ value: c.id, label: `${c.name}${c.shop_name ? ` (${c.shop_name})` : ""}` }));
  const supplierOptions = suppliers.map(s => ({ value: s.id, label: s.name }));
  const productOptions = products.map(p => ({ value: p.id, label: `${p.name} - Rs. ${fmt(p.selling_price)}` }));
  const refOptions = payForm.payment_type === "customer"
    ? invoices.filter(i => !payForm.entity_id || i.customer_id === payForm.entity_id).map(i => ({ value: i.id, label: `${i.invoice_number} - Rs. ${fmt(i.total_amount)}` }))
    : [];

  // ─── Invoice ──────────────────────────────────────────────────────
  const addInvItem = () => setInvForm(f => ({ ...f, items: [...f.items, { product_id: "", product_name: "", quantity: 1, unit_price: "" }] }));
  const updInvItem = (idx, field, value) => setInvForm(f => {
    const items = [...f.items]; items[idx] = { ...items[idx], [field]: value };
    if (field === "product_id") {
      const prod = products.find(p => p.id === value);
      if (prod) { items[idx].product_name = prod.name; items[idx].unit_price = prod.selling_price; }
    }
    return { ...f, items };
  });
  const rmInvItem = (idx) => setInvForm(f => ({ ...f, items: f.items.filter((_, i) => i !== idx) }));
  const invTotal = invForm.items.reduce((s, i) => s + (parseFloat(i.quantity) || 0) * (parseFloat(i.unit_price) || 0), 0);

  const submitHistoricalInvoice = async () => {
    if (!invForm.customer_id) { toast.error("Select customer"); return; }
    if (invForm.items.length === 0) { toast.error("Add at least one item"); return; }
    try {
      const payload = {
        customer_id: invForm.customer_id,
        customer_name: invForm.customer_name,
        customer_shop_name: invForm.customer_shop_name,
        items: invForm.items.map(i => ({ ...i, quantity: parseFloat(i.quantity), unit_price: parseFloat(i.unit_price) })),
        notes: invForm.notes,
      };
      if (invForm.invoice_number) payload.invoice_number = invForm.invoice_number;
      if (invForm.created_at) payload.created_at = invForm.created_at + "T12:00:00";
      await API.post("/invoices", payload);
      toast.success("Historical invoice created");
      setInvForm({ customer_id: "", customer_name: "", customer_shop_name: "", invoice_number: "", created_at: "", items: [], notes: "" });
      load();
    } catch (err) { toast.error(err.response?.data?.detail || "Failed"); }
  };

  // ─── Purchase ─────────────────────────────────────────────────────
  const addPurItem = () => setPurForm(f => ({ ...f, items: [...f.items, { product_id: "", product_name: "", quantity: 1, cost_price: "" }] }));
  const updPurItem = (idx, field, value) => setPurForm(f => {
    const items = [...f.items]; items[idx] = { ...items[idx], [field]: value };
    if (field === "product_id") {
      const prod = products.find(p => p.id === value);
      if (prod) { items[idx].product_name = prod.name; items[idx].cost_price = prod.cost_price; }
    }
    return { ...f, items };
  });
  const rmPurItem = (idx) => setPurForm(f => ({ ...f, items: f.items.filter((_, i) => i !== idx) }));
  const purTotal = purForm.items.reduce((s, i) => s + (parseFloat(i.quantity) || 0) * (parseFloat(i.cost_price) || 0), 0);

  const submitHistoricalPurchase = async () => {
    if (!purForm.supplier_id) { toast.error("Select supplier"); return; }
    if (purForm.items.length === 0) { toast.error("Add at least one item"); return; }
    try {
      const payload = {
        supplier_id: purForm.supplier_id,
        supplier_name: purForm.supplier_name,
        supplier_invoice_number: purForm.supplier_invoice_number,
        items: purForm.items.map(i => ({ ...i, quantity: parseFloat(i.quantity), cost_price: parseFloat(i.cost_price) })),
        notes: purForm.notes,
      };
      if (purForm.purchase_number) payload.purchase_number = purForm.purchase_number;
      if (purForm.created_at) payload.created_at = purForm.created_at + "T12:00:00";
      await API.post("/purchases", payload);
      toast.success("Historical purchase created");
      setPurForm({ supplier_id: "", supplier_name: "", supplier_invoice_number: "", purchase_number: "", created_at: "", items: [], notes: "" });
      load();
    } catch (err) { toast.error(err.response?.data?.detail || "Failed"); }
  };

  // ─── Payment ──────────────────────────────────────────────────────
  const submitHistoricalPayment = async () => {
    if (!payForm.entity_id || !payForm.amount) { toast.error("Entity and amount required"); return; }
    try {
      const payload = {
        payment_type: payForm.payment_type,
        entity_id: payForm.entity_id,
        entity_name: payForm.entity_name,
        amount: parseFloat(payForm.amount),
        payment_method: payForm.payment_method,
        notes: payForm.notes,
        allocations: payForm.reference_id ? [{ reference_id: payForm.reference_id, reference_type: payForm.payment_type === "customer" ? "invoice" : "purchase", amount: parseFloat(payForm.amount) }] : [],
      };
      if (payForm.created_at) payload.created_at = payForm.created_at + "T12:00:00";
      await API.post("/payments", payload);
      toast.success("Historical payment recorded");
      setPayForm({ payment_type: "customer", entity_id: "", entity_name: "", amount: "", payment_method: "cash", created_at: "", reference_id: "", notes: "" });
      load();
    } catch (err) { toast.error(err.response?.data?.detail || "Failed"); }
  };

  // ─── Opening balance ──────────────────────────────────────────────
  const submitOpeningBalance = async () => {
    if (!obForm.entity_id) { toast.error("Select entity"); return; }
    try {
      const endpoint = obForm.entity_type === "customer" ? `/customers/${obForm.entity_id}` : `/suppliers/${obForm.entity_id}`;
      await API.put(endpoint, { opening_balance: parseFloat(obForm.opening_balance) });
      toast.success("Opening balance set");
      setObForm({ entity_type: "customer", entity_id: "", entity_name: "", opening_balance: 0 });
      load();
    } catch (err) { toast.error(err.response?.data?.detail || "Failed"); }
  };

  return (
    <div className="space-y-6" data-testid="migration-page">
      <div className="flex items-center gap-3">
        <History size={28} />
        <div>
          <h1 className="text-3xl sm:text-4xl font-semibold tracking-tight" style={{ fontFamily: 'Outfit, sans-serif' }}>Data Migration</h1>
          <p className="text-sm text-muted-foreground">Enter historical invoices, purchases, payments & opening balances. All entries reflect in reports.</p>
        </div>
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="bg-muted flex-wrap h-auto">
          <TabsTrigger value="invoice" data-testid="mig-invoice-tab">Historical Invoice</TabsTrigger>
          <TabsTrigger value="purchase" data-testid="mig-purchase-tab">Historical Purchase</TabsTrigger>
          <TabsTrigger value="payment" data-testid="mig-payment-tab">Historical Payment</TabsTrigger>
          <TabsTrigger value="opening" data-testid="mig-opening-tab">Opening Balance</TabsTrigger>
        </TabsList>

        {/* Historical Invoice */}
        <TabsContent value="invoice" className="mt-4">
          <Card className="border shadow-sm"><CardContent className="p-6 space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <Label className="text-xs uppercase">Customer *</Label>
                <SearchableSelect options={customerOptions} value={invForm.customer_id} onSelect={id => { const c = customers.find(x => x.id === id); setInvForm(f => ({ ...f, customer_id: id, customer_name: c?.name || "", customer_shop_name: c?.shop_name || "" })); }} placeholder="Select customer..." />
              </div>
              <div><Label className="text-xs uppercase">Invoice Date *</Label><Input type="date" value={invForm.created_at} onChange={e => setInvForm(f => ({ ...f, created_at: e.target.value }))} data-testid="hist-inv-date" /></div>
              <div><Label className="text-xs uppercase">Invoice Number (optional)</Label><Input value={invForm.invoice_number} onChange={e => setInvForm(f => ({ ...f, invoice_number: e.target.value }))} placeholder="Leave blank for auto" data-testid="hist-inv-number" /></div>
            </div>

            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <Label className="text-xs uppercase font-bold">Items</Label>
                <Button type="button" variant="outline" size="sm" onClick={addInvItem} className="rounded-sm text-xs gap-1" data-testid="hist-inv-add-item"><Plus size={12} /> Add Item</Button>
              </div>
              {invForm.items.map((it, idx) => (
                <div key={idx} className="border rounded-sm p-3 bg-[#F8FAFC] space-y-2">
                  <div className="flex justify-between items-center"><span className="text-xs font-bold text-muted-foreground">ITEM {idx + 1}</span>
                    <Button type="button" variant="ghost" size="icon" className="h-6 w-6" onClick={() => rmInvItem(idx)}><X size={14} /></Button></div>
                  <SearchableSelect options={productOptions} value={it.product_id} onSelect={v => updInvItem(idx, "product_id", v)} placeholder="Select product..." />
                  <div className="grid grid-cols-2 gap-3">
                    <Input type="number" placeholder="Qty" value={it.quantity} onChange={e => updInvItem(idx, "quantity", e.target.value)} />
                    <Input type="number" placeholder="Unit Price" value={it.unit_price} onChange={e => updInvItem(idx, "unit_price", e.target.value)} />
                  </div>
                </div>
              ))}
            </div>
            <Textarea placeholder="Notes" value={invForm.notes} onChange={e => setInvForm(f => ({ ...f, notes: e.target.value }))} className="min-h-[50px]" />
            <div className="flex justify-between items-center border-t pt-3">
              <span className="text-lg font-semibold">Total: Rs. {fmt(invTotal)}</span>
              <Button onClick={submitHistoricalInvoice} className="bg-[#0F172A] hover:bg-[#1E293B] rounded-sm" data-testid="submit-hist-invoice">Create Historical Invoice</Button>
            </div>
          </CardContent></Card>
        </TabsContent>

        {/* Historical Purchase */}
        <TabsContent value="purchase" className="mt-4">
          <Card className="border shadow-sm"><CardContent className="p-6 space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <Label className="text-xs uppercase">Supplier *</Label>
                <SearchableSelect options={supplierOptions} value={purForm.supplier_id} onSelect={id => { const s = suppliers.find(x => x.id === id); setPurForm(f => ({ ...f, supplier_id: id, supplier_name: s?.name || "" })); }} placeholder="Select supplier..." />
              </div>
              <div><Label className="text-xs uppercase">Purchase Date *</Label><Input type="date" value={purForm.created_at} onChange={e => setPurForm(f => ({ ...f, created_at: e.target.value }))} data-testid="hist-pur-date" /></div>
              <div><Label className="text-xs uppercase">Supplier Invoice #</Label><Input value={purForm.supplier_invoice_number} onChange={e => setPurForm(f => ({ ...f, supplier_invoice_number: e.target.value }))} placeholder="Supplier's reference" data-testid="hist-pur-supinv" /></div>
              <div><Label className="text-xs uppercase">Purchase Number (optional)</Label><Input value={purForm.purchase_number} onChange={e => setPurForm(f => ({ ...f, purchase_number: e.target.value }))} placeholder="Leave blank for auto" /></div>
            </div>
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <Label className="text-xs uppercase font-bold">Items</Label>
                <Button type="button" variant="outline" size="sm" onClick={addPurItem} className="rounded-sm text-xs gap-1" data-testid="hist-pur-add-item"><Plus size={12} /> Add Item</Button>
              </div>
              {purForm.items.map((it, idx) => (
                <div key={idx} className="border rounded-sm p-3 bg-[#F8FAFC] space-y-2">
                  <div className="flex justify-between items-center"><span className="text-xs font-bold text-muted-foreground">ITEM {idx + 1}</span>
                    <Button type="button" variant="ghost" size="icon" className="h-6 w-6" onClick={() => rmPurItem(idx)}><X size={14} /></Button></div>
                  <SearchableSelect options={productOptions} value={it.product_id} onSelect={v => updPurItem(idx, "product_id", v)} placeholder="Select product..." />
                  <div className="grid grid-cols-2 gap-3">
                    <Input type="number" placeholder="Qty" value={it.quantity} onChange={e => updPurItem(idx, "quantity", e.target.value)} />
                    <Input type="number" placeholder="Cost Price" value={it.cost_price} onChange={e => updPurItem(idx, "cost_price", e.target.value)} />
                  </div>
                </div>
              ))}
            </div>
            <Textarea placeholder="Notes" value={purForm.notes} onChange={e => setPurForm(f => ({ ...f, notes: e.target.value }))} className="min-h-[50px]" />
            <div className="flex justify-between items-center border-t pt-3">
              <span className="text-lg font-semibold">Total: Rs. {fmt(purTotal)}</span>
              <Button onClick={submitHistoricalPurchase} className="bg-[#0F172A] hover:bg-[#1E293B] rounded-sm" data-testid="submit-hist-purchase">Create Historical Purchase</Button>
            </div>
          </CardContent></Card>
        </TabsContent>

        {/* Historical Payment */}
        <TabsContent value="payment" className="mt-4">
          <Card className="border shadow-sm"><CardContent className="p-6 space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <Label className="text-xs uppercase">Payment Type</Label>
                <Select value={payForm.payment_type} onValueChange={v => setPayForm(f => ({ ...f, payment_type: v, entity_id: "", entity_name: "", reference_id: "" }))}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="customer">Customer Payment (Received)</SelectItem>
                    <SelectItem value="supplier">Supplier Payment (Paid)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div><Label className="text-xs uppercase">Date *</Label><Input type="date" value={payForm.created_at} onChange={e => setPayForm(f => ({ ...f, created_at: e.target.value }))} data-testid="hist-pay-date" /></div>
              <div>
                <Label className="text-xs uppercase">{payForm.payment_type === "customer" ? "Customer" : "Supplier"} *</Label>
                <SearchableSelect
                  options={payForm.payment_type === "customer" ? customerOptions : supplierOptions}
                  value={payForm.entity_id}
                  onSelect={id => {
                    const list = payForm.payment_type === "customer" ? customers : suppliers;
                    const e = list.find(x => x.id === id);
                    setPayForm(f => ({ ...f, entity_id: id, entity_name: e?.name || "", reference_id: "" }));
                  }}
                  placeholder="Select..."
                />
              </div>
              <div><Label className="text-xs uppercase">Amount *</Label><Input type="number" value={payForm.amount} onChange={e => setPayForm(f => ({ ...f, amount: e.target.value }))} data-testid="hist-pay-amount" /></div>
              <div>
                <Label className="text-xs uppercase">Method</Label>
                <Select value={payForm.payment_method} onValueChange={v => setPayForm(f => ({ ...f, payment_method: v }))}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent><SelectItem value="cash">Cash</SelectItem><SelectItem value="bank">Bank</SelectItem><SelectItem value="transfer">Transfer</SelectItem><SelectItem value="cheque">Cheque</SelectItem></SelectContent>
                </Select>
              </div>
              {payForm.payment_type === "customer" && (
                <div>
                  <Label className="text-xs uppercase">Link to Invoice (optional)</Label>
                  <SearchableSelect options={refOptions} value={payForm.reference_id} onSelect={v => setPayForm(f => ({ ...f, reference_id: v }))} placeholder="Select invoice..." />
                </div>
              )}
            </div>
            <Textarea placeholder="Notes" value={payForm.notes} onChange={e => setPayForm(f => ({ ...f, notes: e.target.value }))} className="min-h-[50px]" />
            <div className="flex justify-end border-t pt-3">
              <Button onClick={submitHistoricalPayment} className="bg-[#0F172A] hover:bg-[#1E293B] rounded-sm" data-testid="submit-hist-payment">Record Historical Payment</Button>
            </div>
          </CardContent></Card>
        </TabsContent>

        {/* Opening Balance */}
        <TabsContent value="opening" className="mt-4">
          <Card className="border shadow-sm"><CardContent className="p-6 space-y-4">
            <p className="text-xs text-muted-foreground">Set the opening outstanding/payable for an existing customer or supplier. This adds directly to their total — use for migrating pre-existing balances that have no linked invoices/purchases.</p>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <Label className="text-xs uppercase">Type</Label>
                <Select value={obForm.entity_type} onValueChange={v => setObForm(f => ({ ...f, entity_type: v, entity_id: "", entity_name: "" }))}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent><SelectItem value="customer">Customer</SelectItem><SelectItem value="supplier">Supplier</SelectItem></SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-xs uppercase">{obForm.entity_type === "customer" ? "Customer" : "Supplier"}</Label>
                <SearchableSelect
                  options={obForm.entity_type === "customer" ? customerOptions : supplierOptions}
                  value={obForm.entity_id}
                  onSelect={id => {
                    const list = obForm.entity_type === "customer" ? customers : suppliers;
                    const e = list.find(x => x.id === id);
                    setObForm(f => ({ ...f, entity_id: id, entity_name: e?.name || "", opening_balance: e?.opening_balance || 0 }));
                  }}
                  placeholder="Select..."
                />
              </div>
              <div><Label className="text-xs uppercase">Opening Balance *</Label><Input type="number" value={obForm.opening_balance} onChange={e => setObForm(f => ({ ...f, opening_balance: e.target.value }))} data-testid="hist-opening-amount" /></div>
            </div>
            <div className="flex justify-end border-t pt-3">
              <Button onClick={submitOpeningBalance} className="bg-[#0F172A] hover:bg-[#1E293B] rounded-sm" data-testid="submit-opening-balance">Save Opening Balance</Button>
            </div>
          </CardContent></Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
