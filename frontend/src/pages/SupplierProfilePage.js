import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import API from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { ArrowLeft, CreditCard, FileText, Package } from "lucide-react";

const fmt = (n) => new Intl.NumberFormat("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n || 0);

export default function SupplierProfilePage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [supplier, setSupplier] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    API.get(`/suppliers/${id}`).then(r => setSupplier(r.data)).catch(console.error).finally(() => setLoading(false));
  }, [id]);

  if (loading) return <div className="p-8 text-center text-muted-foreground">Loading...</div>;
  if (!supplier) return <div className="p-8 text-center text-muted-foreground">Supplier not found</div>;

  return (
    <div className="space-y-6" data-testid="supplier-profile-page">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={() => navigate("/suppliers")} data-testid="back-to-suppliers"><ArrowLeft size={18} /></Button>
        <div>
          <h1 className="text-3xl font-semibold tracking-tight" style={{ fontFamily: 'Outfit, sans-serif' }}>{supplier.name}</h1>
          {supplier.phone && <p className="text-muted-foreground text-sm">{supplier.phone}</p>}
          {supplier.is_primary && <Badge className="bg-[#0F172A] text-white text-xs rounded-full mt-1">Primary Supplier</Badge>}
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card className="border shadow-sm"><CardContent className="p-5">
          <div className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-2">Total Payable</div>
          <div className="text-2xl font-semibold" style={{ fontFamily: 'Outfit, sans-serif' }}>
            <span className={supplier.payable > 0 ? "text-red-600" : "text-emerald-600"}>Rs. {fmt(supplier.payable)}</span>
          </div>
        </CardContent></Card>

        <Card className="border shadow-sm"><CardContent className="p-5">
          <div className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-2">Last Payment</div>
          <div className="text-2xl font-semibold" style={{ fontFamily: 'Outfit, sans-serif' }}>
            {supplier.last_payment ? `Rs. ${fmt(supplier.last_payment.amount)}` : "N/A"}
          </div>
          {supplier.last_payment && <p className="text-xs text-muted-foreground mt-1">{supplier.last_payment.created_at?.slice(0, 10)}</p>}
        </CardContent></Card>

        <Card className="border shadow-sm"><CardContent className="p-5">
          <div className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-2">Total Purchases</div>
          <div className="text-2xl font-semibold" style={{ fontFamily: 'Outfit, sans-serif' }}>{supplier.purchases?.length || 0}</div>
        </CardContent></Card>
      </div>

      {/* Fast Moving Items */}
      {supplier.fast_moving_items?.length > 0 && (
        <Card className="border shadow-sm">
          <CardContent className="p-5">
            <h3 className="text-sm font-bold uppercase tracking-wider text-muted-foreground mb-4 flex items-center gap-2"><Package size={14} /> Fast Moving Items</h3>
            <div className="space-y-2">
              {supplier.fast_moving_items.map((item, idx) => (
                <div key={idx} className="flex items-center justify-between py-2 border-b border-dashed last:border-0">
                  <span className="text-sm font-medium">{item.product}</span>
                  <span className="text-sm text-muted-foreground">{item.quantity} units</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      <Separator />

      {/* Purchases */}
      <Card className="border shadow-sm">
        <CardContent className="p-5">
          <h3 className="text-sm font-bold uppercase tracking-wider text-muted-foreground mb-4 flex items-center gap-2"><FileText size={14} /> Purchases</h3>
          {supplier.purchases?.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="data-table w-full">
                <thead><tr><th>Purchase #</th><th>Order #</th><th>Amount</th><th>Type</th><th>Date</th></tr></thead>
                <tbody>
                  {supplier.purchases.map(p => (
                    <tr key={p.id}>
                      <td className="font-medium">{p.purchase_number}</td>
                      <td>{p.order_number || "-"}</td>
                      <td>Rs. {fmt(p.total_amount)}</td>
                      <td><Badge variant="secondary" className="text-xs rounded-full">{p.auto_generated ? "Auto" : "Manual"}</Badge></td>
                      <td className="text-muted-foreground">{p.created_at?.slice(0, 10)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <p className="text-sm text-muted-foreground">No purchases yet.</p>}
        </CardContent>
      </Card>

      {/* Payments */}
      <Card className="border shadow-sm">
        <CardContent className="p-5">
          <h3 className="text-sm font-bold uppercase tracking-wider text-muted-foreground mb-4 flex items-center gap-2"><CreditCard size={14} /> Payments</h3>
          {supplier.payments?.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="data-table w-full">
                <thead><tr><th>Amount</th><th>Method</th><th>Notes</th><th>Date</th></tr></thead>
                <tbody>
                  {supplier.payments.map(p => (
                    <tr key={p.id}>
                      <td className="font-semibold">Rs. {fmt(p.amount)}</td>
                      <td><Badge variant="secondary" className="text-xs rounded-full">{p.payment_method}</Badge></td>
                      <td className="text-muted-foreground text-sm">{p.notes || "-"}</td>
                      <td className="text-muted-foreground">{p.created_at?.slice(0, 10)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <p className="text-sm text-muted-foreground">No payments yet.</p>}
        </CardContent>
      </Card>
    </div>
  );
}
