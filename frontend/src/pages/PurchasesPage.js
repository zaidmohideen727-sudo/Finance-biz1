import { useState, useEffect, useCallback } from "react";
import API from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { SearchableSelect } from "@/components/SearchableSelect";
import { toast } from "sonner";
import { Plus, Search, Trash2, FileText, X } from "lucide-react";

const fmt = (n) => new Intl.NumberFormat("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n || 0);

export default function PurchasesPage() {
  const [purchases, setPurchases] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [products, setProducts] = useState([]);
  const [orders, setOrders] = useState([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState({ supplier_id: "", supplier_name: "", order_id: "", order_number: "", items: [], notes: "" });

  const fetchPurchases = useCallback(async () => {
    try {
      const { data } = await API.get("/purchases", { params: { search: search || undefined } });
      setPurchases(data);
    } catch (err) { console.error(err); }
    finally { setLoading(false); }
  }, [search]);

  const fetchMasterData = useCallback(async () => {
    try {
      const [s, p, o] = await Promise.all([API.get("/suppliers"), API.get("/products"), API.get("/orders")]);
      setSuppliers(s.data);
      setProducts(p.data);
      setOrders(o.data);
    } catch (err) { console.error(err); }
  }, []);

  useEffect(() => { fetchPurchases(); fetchMasterData(); }, [fetchPurchases, fetchMasterData]);

  const supplierOptions = suppliers.map(s => ({ value: s.id, label: s.name }));
  const productOptions = products.map(p => ({ value: p.id, label: `${p.name} - Rs. ${fmt(p.cost_price || p.selling_price)}` }));
  const orderOptions = orders.map(o => ({ value: o.id, label: `${o.order_number} - ${o.customer_name}` }));

  const openNew = () => {
    setForm({ supplier_id: "", supplier_name: "", order_id: "", order_number: "", items: [], notes: "" });
    setDialogOpen(true);
  };

  const selectSupplier = (id) => {
    const sup = suppliers.find(s => s.id === id);
    setForm(f => ({ ...f, supplier_id: id, supplier_name: sup?.name || "" }));
  };

  const selectOrder = (id) => {
    const ord = orders.find(o => o.id === id);
    setForm(f => ({ ...f, order_id: id, order_number: ord?.order_number || "" }));
  };

  const addItem = () => setForm(f => ({ ...f, items: [...f.items, { product_id: "", product_name: "", quantity: 1, cost_price: "" }] }));

  const updateItem = (idx, field, value) => {
    setForm(f => {
      const items = [...f.items];
      items[idx] = { ...items[idx], [field]: value };
      if (field === "product_id") {
        const prod = products.find(p => p.id === value);
        if (prod) { items[idx].product_name = prod.name; items[idx].cost_price = prod.cost_price || 0; }
      }
      return { ...f, items };
    });
  };

  const removeItem = (idx) => setForm(f => ({ ...f, items: f.items.filter((_, i) => i !== idx) }));
  const purchaseTotal = form.items.reduce((s, i) => s + ((parseFloat(i.quantity) || 0) * (parseFloat(i.cost_price) || 0)), 0);

  const handleCreate = async () => {
    if (!form.supplier_id) { toast.error("Select a supplier"); return; }
    if (form.items.length === 0) { toast.error("Add at least one item"); return; }
    try {
      await API.post("/purchases", form);
      toast.success("Purchase recorded");
      setDialogOpen(false);
      fetchPurchases();
    } catch (err) { toast.error(err.response?.data?.detail || "Failed to create"); }
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Delete this purchase?")) return;
    try {
      await API.delete(`/purchases/${id}`);
      toast.success("Purchase deleted");
      fetchPurchases();
    } catch (err) { toast.error("Failed to delete"); }
  };

  return (
    <div className="space-y-6" data-testid="purchases-page">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-3xl sm:text-4xl font-semibold tracking-tight" style={{ fontFamily: 'Outfit, sans-serif' }}>Purchases</h1>
        <Button onClick={openNew} className="bg-[#0F172A] hover:bg-[#1E293B] rounded-sm gap-2" data-testid="add-purchase-button">
          <Plus size={16} /> Record Purchase
        </Button>
      </div>

      <div className="relative max-w-sm">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
        <Input placeholder="Search purchases..." value={search} onChange={e => setSearch(e.target.value)} className="pl-9" data-testid="purchase-search-input" />
      </div>

      <Card className="border shadow-sm">
        <CardContent className="p-0">
          {loading ? (
            <div className="p-8 text-center text-muted-foreground">Loading...</div>
          ) : purchases.length === 0 ? (
            <div className="p-8 text-center text-muted-foreground">
              <FileText size={32} className="mx-auto mb-2 opacity-30" />
              No purchases recorded yet.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="data-table w-full">
                <thead><tr><th>Purchase #</th><th>Supplier</th><th>Order #</th><th>Items</th><th>Amount</th><th>Date</th><th className="w-16">Actions</th></tr></thead>
                <tbody>
                  {purchases.map(p => (
                    <tr key={p.id}>
                      <td className="font-medium">{p.purchase_number}</td>
                      <td>{p.supplier_name}</td>
                      <td>{p.order_number || "-"}</td>
                      <td>{p.items?.length || 0}</td>
                      <td>{"Rs. "}{fmt(p.total_amount)}</td>
                      <td className="text-muted-foreground">{p.created_at?.slice(0, 10)}</td>
                      <td>
                        <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive" onClick={() => handleDelete(p.id)} data-testid={`delete-purchase-${p.id}`}>
                          <Trash2 size={14} />
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader><DialogTitle style={{ fontFamily: 'Outfit, sans-serif' }}>Record Purchase</DialogTitle></DialogHeader>
          <div className="space-y-4 py-2">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label className="text-xs font-bold uppercase tracking-wider">Supplier *</Label>
                <SearchableSelect options={supplierOptions} value={form.supplier_id} onSelect={selectSupplier} placeholder="Select supplier..." />
              </div>
              <div className="space-y-2">
                <Label className="text-xs font-bold uppercase tracking-wider">Linked Order (optional)</Label>
                <SearchableSelect options={orderOptions} value={form.order_id} onSelect={selectOrder} placeholder="Link to order..." />
              </div>
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label className="text-xs font-bold uppercase tracking-wider">Items</Label>
                <Button type="button" variant="outline" size="sm" onClick={addItem} className="gap-1 text-xs rounded-sm" data-testid="add-purchase-item-button"><Plus size={14} /> Add Item</Button>
              </div>
              {form.items.map((item, idx) => (
                <div key={idx} className="border rounded-sm p-3 space-y-2 bg-[#F8FAFC]">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-muted-foreground">ITEM {idx + 1}</span>
                    <Button type="button" variant="ghost" size="icon" className="h-6 w-6" onClick={() => removeItem(idx)}><X size={14} /></Button>
                  </div>
                  <SearchableSelect options={productOptions} value={item.product_id} onSelect={v => updateItem(idx, "product_id", v)} placeholder="Select product..." />
                  <div className="grid grid-cols-2 gap-3">
                    <div><Label className="text-xs">Quantity</Label><Input type="number" min="1" value={item.quantity} onChange={e => updateItem(idx, "quantity", e.target.value === "" ? "" : parseFloat(e.target.value))} /></div>
                    <div><Label className="text-xs">Cost Price</Label><Input type="number" value={item.cost_price} onChange={e => updateItem(idx, "cost_price", e.target.value === "" ? "" : parseFloat(e.target.value))} placeholder="Cost price" /></div>
                  </div>
                  <div className="text-right text-sm font-medium">Amount: {"Rs. "}{fmt((parseFloat(item.quantity) || 0) * (parseFloat(item.cost_price) || 0))}</div>
                </div>
              ))}
            </div>

            <Textarea value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} placeholder="Notes (optional)" className="min-h-[60px]" />

            <div className="text-right text-lg font-semibold border-t pt-3" style={{ fontFamily: 'Outfit, sans-serif' }}>
              Total: {"Rs. "}{fmt(purchaseTotal)}
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)} className="rounded-sm">Cancel</Button>
            <Button onClick={handleCreate} className="bg-[#0F172A] hover:bg-[#1E293B] rounded-sm" data-testid="submit-purchase-button">Record Purchase</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
