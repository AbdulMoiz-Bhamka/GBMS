import { useEffect, useState } from 'react'
import { PackageCheck, Printer, RefreshCw, Truck } from 'lucide-react'
import { goodsReceiptService } from '../../services/goodsReceiptService'

function LotLabel({ label, onClose }) {
  return <div className="fixed inset-0 z-[90] flex items-center justify-center bg-slate-900/40 p-4" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose() }}><section className="w-full max-w-md rounded-2xl bg-white p-5 shadow-xl"><div id="material-lot-label" className="border border-slate-300 p-4"><p className="text-center text-xs font-bold uppercase">{label.company_name}</p><h2 className="mt-2 text-center font-bold">{label.product_name}</h2><p className="mt-1 text-center font-mono text-xs">{label.sku} · Lot {label.lot_number}</p><p className="mt-1 text-center text-xs">Supplier: {label.supplier_name} · PO: {label.purchase_order_number}</p><p className="mt-1 text-center text-xs">Received: {label.original_quantity} {label.unit_code}</p><img className="mx-auto mt-3 max-h-14 max-w-full" src={`data:image/svg+xml;base64,${label.barcode_svg_base64}`} alt={`Material lot barcode ${label.barcode_value}`} /><p className="text-center font-mono text-[10px]">{label.barcode_value}</p></div><div className="mt-4 flex justify-end gap-2"><button type="button" onClick={onClose} className="rounded-lg border px-4 py-2">Close</button><button type="button" onClick={() => window.print()} className="inline-flex items-center gap-2 rounded-lg bg-sky-700 px-4 py-2 text-white"><Printer size={16} />Print lot label</button></div><style>{`@media print{body *{visibility:hidden!important}#material-lot-label,#material-lot-label *{visibility:visible!important}#material-lot-label{position:fixed;inset:0;width:80mm;height:50mm;padding:4mm!important;border:0!important}}`}</style></section></div>
}

export default function GoodsReceiptsPage() {
  const [orders, setOrders] = useState([])
  const [lines, setLines] = useState([])
  const [lots, setLots] = useState([])
  const [orderId, setOrderId] = useState('')
  const [formLines, setFormLines] = useState({})
  const [notes, setNotes] = useState('')
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [label, setLabel] = useState(null)

  const load = async () => {
    setLoading(true)
    try {
      // Load options (open POs) and lots independently so a lots DB error
      // doesn't block the purchase order dropdown from loading.
      const optionsResult = await goodsReceiptService.options()
      setOrders(optionsResult.purchase_orders)
      setError('')

      try {
        const lotResult = await goodsReceiptService.lots()
        setLots(lotResult.items)
      } catch (lotFailure) {
        // Lots may 500 if the manufacturing tables haven't been migrated yet.
        // Show a warning but keep the receipt form usable.
        setLots([])
        const msg = lotFailure.message || ''
        if (msg.toLowerCase().includes('invalid object name') || lotFailure.status === 500) {
          setError('Material lot history is unavailable — the manufacturing database migration may not have been applied yet. The goods receipt form is still functional.')
        }
      }
    } catch (failure) {
      setError(failure.message || 'Could not load goods receipt data.')
    } finally {
      setLoading(false)
    }
  }
  useEffect(() => { load() }, [])

  const selectOrder = async (value) => {
    setOrderId(value); setLines([]); setFormLines({}); setError('')
    if (!value) return
    try {
      const options = await goodsReceiptService.options(Number(value))
      // Show all lines with outstanding quantity, regardless of product type.
      // The backend enforces that only RAW_MATERIAL products can be received;
      // if a line is FINISHED_GOOD, posting will return a clear error from the API.
      const outstanding = options.items.filter((item) => Number(item.outstanding_quantity) > 0)
      setLines(outstanding)
      setFormLines(Object.fromEntries(outstanding.map((item) => [item.purchase_order_item_id, { quantity: '', lot_number: '' }])))
      if (outstanding.length === 0 && options.items.length > 0) {
        setError('All lines on this order have been fully received.')
      } else if (options.items.length === 0) {
        setError('This purchase order has no product lines.')
      }
    } catch (failure) { setError(failure.message || 'Could not load purchase order lines.') }
  }

  const submit = async (event) => {
    event.preventDefault()
    const items = lines.filter((line) => formLines[line.purchase_order_item_id]?.quantity)
    if (!items.length) { setError('Enter a received quantity for at least one line.'); return }
    setBusy(true); setError(''); setSuccess('')
    try {
      const receipt = await goodsReceiptService.create({
        purchase_order_id: Number(orderId), notes: notes.trim() || null,
        idempotency_key: crypto.randomUUID(),
        items: items.map((line) => ({ purchase_order_item_id: line.purchase_order_item_id,
          product_id: line.product_id, received_quantity: formLines[line.purchase_order_item_id].quantity,
          lot_number: formLines[line.purchase_order_item_id].lot_number.trim() || null })),
      })
      setSuccess(`Receipt ${receipt.receipt_number} posted. ${receipt.items.length} material lot(s) were created and stock was updated.`)
      setOrderId(''); setLines([]); setFormLines({}); setNotes('')
      window.dispatchEvent(new Event('gbms:inventory-stock-changed'))
      await load()
    } catch (failure) { setError(failure.message || 'Could not post this goods receipt.') }
    finally { setBusy(false) }
  }

  const printLot = async (lotId) => {
    try { setLabel(await goodsReceiptService.lotLabel(lotId)) }
    catch (failure) { setError(failure.message || 'Could not load this material lot label.') }
  }

  return <section className="space-y-6 text-slate-800">
    <header className="flex items-end justify-between gap-3"><div><p className="text-sm font-semibold uppercase tracking-wider text-sky-700">Company operations</p><h1 className="mt-2 text-3xl font-semibold">Goods receipt</h1><p className="mt-2 text-slate-500">Receive a supplier delivery against an open purchase order. Each delivery is traceable by its material lot.</p></div><button type="button" onClick={load} className="inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm"><RefreshCw size={15} />Refresh</button></header>
    {error && <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">{error}</p>}{success && <p role="status" className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{success}</p>}
    <form onSubmit={submit} className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><div className="flex items-center gap-3"><span className="rounded-xl bg-sky-50 p-3 text-sky-700"><Truck size={20} /></span><div><h2 className="font-semibold">Record a supplier delivery</h2><p className="text-sm text-slate-500">Partial deliveries are supported; excess quantities are rejected. Only <strong>submitted</strong> purchase orders appear here — draft orders must be submitted first.</p></div></div><label className="block text-sm font-medium">Purchase order *<select required value={orderId} onChange={(event) => selectOrder(event.target.value)} className="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2"><option value="">Select a submitted purchase order</option>{orders.map((order) => <option key={order.purchase_order_id} value={order.purchase_order_id}>{order.purchase_order_number} · {order.supplier_name} · {order.status}</option>)}</select>{!loading && orders.length === 0 && <p className="mt-1.5 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">No submitted purchase orders found. Open <strong>Purchase Orders</strong>, submit a draft order, then return here to receive goods against it.</p>}</label>
      {lines.length > 0 && <div className="overflow-x-auto rounded-xl border border-slate-200"><table className="w-full min-w-[800px] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase text-slate-500"><tr>{['Material','SKU','Type','Ordered','Received','Outstanding','Receive now','Lot number (optional)'].map((title) => <th key={title} className="px-3 py-2">{title}</th>)}</tr></thead><tbody className="divide-y">{lines.map((line) => <tr key={line.purchase_order_item_id} className={line.product_type !== 'RAW_MATERIAL' ? 'bg-amber-50' : ''}><td className="px-3 py-3">{line.product_name}<p className="text-xs text-slate-500">{line.design || ''} {line.size || ''} {line.color || ''}</p></td><td className="px-3 py-3 font-mono text-xs">{line.sku}</td><td className="px-3 py-3"><span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${line.product_type === 'RAW_MATERIAL' ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-100 text-amber-800'}`}>{line.product_type === 'RAW_MATERIAL' ? 'Raw material' : 'Finished good — cannot receive'}</span></td><td className="px-3 py-3">{line.ordered_quantity} {line.unit_code}</td><td className="px-3 py-3">{line.received_quantity}</td><td className="px-3 py-3">{line.outstanding_quantity}</td><td className="px-3 py-3">{line.product_type === 'RAW_MATERIAL' ? <input aria-label={`Received quantity for ${line.sku}`} type="number" min="0" max={line.outstanding_quantity} step="0.001" value={formLines[line.purchase_order_item_id]?.quantity || ''} onChange={(event) => setFormLines({ ...formLines, [line.purchase_order_item_id]: { ...formLines[line.purchase_order_item_id], quantity: event.target.value } })} className="w-28 rounded-lg border px-2 py-1.5" /> : <span className="text-xs text-amber-700">Change product type to Raw material first</span>}</td><td className="px-3 py-3">{line.product_type === 'RAW_MATERIAL' ? <input aria-label={`Lot number for ${line.sku}`} maxLength={60} value={formLines[line.purchase_order_item_id]?.lot_number || ''} onChange={(event) => setFormLines({ ...formLines, [line.purchase_order_item_id]: { ...formLines[line.purchase_order_item_id], lot_number: event.target.value } })} placeholder="Generated if blank" className="w-40 rounded-lg border px-2 py-1.5" /> : '—'}</td></tr>)}</tbody></table></div>}
      {orderId && lines.length === 0 && !error && <p className="rounded-lg bg-slate-50 p-3 text-sm text-slate-500">No outstanding product lines found for this order.</p>}
      <label className="block text-sm font-medium">Receipt notes<textarea rows={2} maxLength={1000} value={notes} onChange={(event) => setNotes(event.target.value)} className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2" /></label><div className="flex justify-end"><button disabled={busy || !lines.length} className="inline-flex items-center gap-2 rounded-lg bg-sky-700 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50"><PackageCheck size={17} />{busy ? 'Posting receipt…' : 'Post goods receipt'}</button></div>
    </form>
    <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm"><div className="border-b p-5"><h2 className="font-semibold">Received material lots</h2><p className="text-sm text-slate-500">Print a unique lot barcode for tracking materials from each delivery.</p></div>{loading ? <p className="p-8 text-center text-sm text-slate-500">Loading lots…</p> : lots.length === 0 ? <p className="p-10 text-center text-sm text-slate-500">No receipt lots yet.</p> : <div className="overflow-x-auto"><table className="w-full min-w-[900px] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase text-slate-500"><tr>{['Lot','Material','Supplier / PO','Received','Remaining','Date','Label'].map((title) => <th key={title} className="px-4 py-3">{title}</th>)}</tr></thead><tbody className="divide-y">{lots.map((lot) => <tr key={lot.material_lot_id}><td className="px-4 py-3 font-mono text-xs">{lot.lot_number}</td><td className="px-4 py-3">{lot.product_name}<p className="text-xs text-slate-500">{lot.sku}</p></td><td className="px-4 py-3">{lot.supplier_name}<p className="text-xs text-slate-500">{lot.purchase_order_number} / {lot.receipt_number}</p></td><td className="px-4 py-3">{lot.original_quantity} {lot.unit_code}</td><td className="px-4 py-3">{lot.remaining_quantity} {lot.unit_code}</td><td className="px-4 py-3">{new Date(lot.created_at).toLocaleDateString()}</td><td className="px-4 py-3"><button type="button" onClick={() => printLot(lot.material_lot_id)} className="inline-flex items-center gap-1 rounded-lg border px-3 py-1.5 text-xs"><Printer size={14} />Print lot</button></td></tr>)}</tbody></table></div>}</section>
    {label && <LotLabel label={label} onClose={() => setLabel(null)} />}
  </section>
}
