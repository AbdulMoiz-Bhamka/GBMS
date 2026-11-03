import { useCallback, useEffect, useRef, useState } from 'react'
import { Barcode, Camera, LoaderCircle, Printer, Search, Tag, X } from 'lucide-react'
import { barcodeService } from '../../services/barcodeService'
import { useAuth } from '../../auth/useAuth'

const field = 'input input-bordered w-full bg-white'
const select = 'select select-bordered w-full bg-white'
const button = 'btn btn-primary'

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]))
}

function printLabels(labels, copies) {
  const cards = Array.from({ length: copies }, () => `<article class="label"><small>${escapeHtml(labels.company_name || 'GBMS')}</small><h2>${escapeHtml(labels.product_name)}</h2><p>${escapeHtml([labels.design, labels.size, labels.color].filter(Boolean).join(' · '))}</p><b>SKU: ${escapeHtml(labels.sku)}</b><img src="data:image/svg+xml;base64,${labels.barcode_svg_base64}"/><strong>${escapeHtml(labels.barcode_value)}</strong><p>PKR ${Number(labels.selling_price || 0).toFixed(2)}</p></article>`).join('')
  const page = window.open('', '_blank', 'width=800,height=700')
  if (!page) return
  page.document.write(`<!doctype html><html><head><title>Garment labels</title><style>@page{margin:8mm}.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:8mm}.label{border:1px solid #ccd6df;border-radius:8px;padding:5mm;text-align:center;break-inside:avoid;font:12px Arial;color:#142b3c}.label img{display:block;width:90%;height:20mm;object-fit:contain;margin:3mm auto}.label h2{font-size:15px;margin:3px}.label p{margin:4px}</style></head><body><main class="grid">${cards}</main><scr${'ipt'}>window.onload=()=>window.print()</scr${'ipt'}></body></html>`)
  page.document.close()
}

export default function BarcodesPage() {
  const { user } = useAuth()
  const canCreate = user?.permissions?.includes('inventory.create')
  const canUpdate = user?.permissions?.includes('inventory.update')
  const [options, setOptions] = useState({ categories: [], units: [], raw_materials: [] })
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [pageOffset, setPageOffset] = useState(0)
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('ALL')
  const [category, setCategory] = useState('')
  const [size, setSize] = useState('')
  const [color, setColor] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const [creating, setCreating] = useState(false)
  const [scan, setScan] = useState('')
  const [scanResult, setScanResult] = useState(null)
  const [details, setDetails] = useState(null)
  const [editingMaterials, setEditingMaterials] = useState(false)
  const [detailMaterials, setDetailMaterials] = useState([])
  const [cameraMessage, setCameraMessage] = useState('')
  const video = useRef(null)
  const stream = useRef(null)
  const [copies, setCopies] = useState(1)
  const [materials, setMaterials] = useState([])

  const reload = useCallback(async () => {
    try {
      const result = await barcodeService.list({ search, size, color, status, category_id: category, limit: 100, offset: pageOffset })
      setItems(result.items || [])
      setTotal(result.total || 0)
    } catch (error) {
      setNotice(error.message || 'Could not load finished goods. Check the database migration and backend logs.')
    }
  }, [search, size, color, status, category, pageOffset])

  useEffect(() => {
    let active = true
    barcodeService.options().then((catalog) => { if (active) setOptions(catalog) }).catch((error) => { if (active) setNotice(error.message) })
    return () => { active = false }
  }, [])
  useEffect(() => {
    let active = true
    const timeout = window.setTimeout(() => {
      barcodeService.list({ search, size, color, status, category_id: category, limit: 100, offset: pageOffset })
        .then((result) => { if (active) { setItems(result.items || []); setTotal(result.total || 0) } })
        .catch((error) => { if (active) setNotice(error.message || 'Could not load finished goods.') })
    }, 350)
    return () => { active = false; window.clearTimeout(timeout) }
  }, [search, size, color, status, category, pageOffset])
  useEffect(() => () => { stream.current?.getTracks().forEach((track) => track.stop()); stream.current = null }, [])

  async function action(id, fn) {
    setBusy(true); setNotice('')
    try { const label = await fn(id); setNotice('Barcode ready. The barcode value identifies this product variant only.'); await reload(); return label }
    catch (error) { setNotice(error.message || 'Request could not be completed.') }
    finally { setBusy(false) }
  }

  async function submitProduct(event) {
    event.preventDefault(); setBusy(true); setNotice('')
    const form = event.currentTarget
    const data = new FormData(form)
    const payload = Object.fromEntries(['sku','product_name','unit_id','category_id','description','design','size','color','selling_price'].map((key) => [key, data.get(key)]))
    payload.unit_id = Number(payload.unit_id); payload.category_id = payload.category_id ? Number(payload.category_id) : null
    payload.materials = materials.filter((part) => part.product_id && part.quantity_per_finished_unit).map((part) => ({ product_id: Number(part.product_id), quantity_per_finished_unit: Number(part.quantity_per_finished_unit) }))
    try {
      const created = await barcodeService.create(payload)
      const label = await barcodeService.generate(created.product_id)
      setCreating(false); setMaterials([]); form.reset(); setNotice('Finished good saved with zero on-hand quantity; barcode generated.'); await reload()
      if (label) printLabels({ ...label, company_name: options.company_name }, 1)
    } catch (error) { setNotice(error.message || 'Could not save the finished good.') }
    finally { setBusy(false) }
  }

  async function doLookup(value = scan) {
    if (!value.trim()) return
    try { setScanResult(await barcodeService.lookup(value.trim())); setNotice('Barcode found. Looking it up did not change stock.') }
    catch (error) { setScanResult(null); setNotice(error.message || 'Barcode was not found in this company.') }
  }

  async function startCamera() {
    if (!('BarcodeDetector' in window) || !navigator.mediaDevices?.getUserMedia) { setCameraMessage('This browser does not support camera barcode detection. Use a USB scanner or type/paste the barcode below.'); return }
    try {
      stream.current = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } })
      video.current.srcObject = stream.current; await video.current.play()
      const detector = new window.BarcodeDetector({ formats: ['code_128'] })
      setCameraMessage('Point the camera at a Code 128 label.')
      const detect = async () => {
        if (!stream.current) return
        try { const codes = await detector.detect(video.current); if (codes[0]?.rawValue) { setScan(codes[0].rawValue); doLookup(codes[0].rawValue); stream.current.getTracks().forEach((track) => track.stop()); stream.current = null; return } } catch { /* wait for next camera frame */ }
        requestAnimationFrame(detect)
      }
      requestAnimationFrame(detect)
    } catch { setCameraMessage('Camera access failed. Use a USB scanner or manual lookup.') }
  }

  const print = async (id) => { const label = await action(id, barcodeService.label); if (label) printLabels(label, Math.max(1, Math.min(200, Number(copies) || 1))) }
  const showDetails = async (id) => { const result = await action(id, barcodeService.label); if (result) setDetails(result) }
  async function saveMaterialPlan() {
    setBusy(true)
    try {
      await barcodeService.updateMaterials(details.product_id, detailMaterials.filter((part) => part.product_id && part.quantity_per_finished_unit).map((part) => ({ product_id: Number(part.product_id), quantity_per_finished_unit: Number(part.quantity_per_finished_unit) })))
      const updated = await barcodeService.label(details.product_id); setDetails(updated); setEditingMaterials(false); setNotice('Planned raw materials updated. Inventory quantities were not changed.')
    } catch (error) { setNotice(error.message || 'Could not update the material plan.') }
    finally { setBusy(false) }
  }

  return <main className="mx-auto max-w-[1500px] space-y-6 p-6 lg:p-8">
    <header className="flex flex-wrap items-end justify-between gap-4"><div><p className="text-xs font-semibold uppercase tracking-widest text-sky-700">Company operations</p><h1 className="mt-2 text-3xl font-semibold text-slate-900">Finished goods &amp; barcodes</h1><p className="mt-2 text-sm text-slate-500">Manage garment variants, barcode labels and read-only product lookup.</p></div>{canCreate&&<button className={button} onClick={() => setCreating(!creating)}><Tag size={17}/>{creating ? 'Close form' : 'Add finished good'}</button>}</header>
    {notice && <div role="status" className="alert border border-sky-100 bg-sky-50 text-sky-900">{notice}<button className="btn btn-ghost btn-xs ml-auto" onClick={() => setNotice('')} aria-label="Dismiss"><X size={16}/></button></div>}
    {creating && <form onSubmit={submitProduct} className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"><h2 className="text-lg font-semibold">Finished garment details</h2><p className="mb-5 mt-1 text-sm text-slate-500">New records start with zero on-hand stock. Barcode generation never adjusts inventory.</p>
      <div className="grid gap-4 md:grid-cols-3"><label className="form-control"><span className="label-text mb-1">SKU *</span><input name="sku" required maxLength="60" className={field}/></label><label className="form-control"><span className="label-text mb-1">Product name *</span><input name="product_name" required maxLength="180" className={field}/></label><label className="form-control"><span className="label-text mb-1">Category</span><select name="category_id" className={select}><option value="">No category</option>{options.categories.map((x)=><option key={x.id} value={x.id}>{x.name}</option>)}</select></label>
      <label className="form-control"><span className="label-text mb-1">Unit *</span><select name="unit_id" required className={select}><option value="">Select unit</option>{options.units.map((x)=><option key={x.id} value={x.id}>{x.name} ({x.symbol})</option>)}</select></label><label className="form-control"><span className="label-text mb-1">Design</span><input name="design" className={field}/></label><label className="form-control"><span className="label-text mb-1">Size</span><input name="size" className={field}/></label><label className="form-control"><span className="label-text mb-1">Colour</span><input name="color" className={field}/></label><label className="form-control"><span className="label-text mb-1">Selling price (PKR) *</span><input name="selling_price" type="number" min="0" step="0.01" required className={field}/></label><label className="form-control md:col-span-1"><span className="label-text mb-1">Description / fabric details</span><input name="description" maxLength="1000" className={field}/></label></div>
      <div className="mt-6"><div className="flex items-center justify-between"><h3 className="font-semibold">Planned raw materials per garment</h3><button type="button" className="btn btn-outline btn-sm" onClick={()=>setMaterials((v)=>[...v,{product_id:'',quantity_per_finished_unit:''}])}>Add material</button></div><p className="mt-1 text-xs text-slate-500">This is a bill of materials, not proof of actual consumption or lot traceability.</p>{materials.map((part,index)=><div className="mt-3 grid gap-3 md:grid-cols-[1fr_220px_auto]" key={index}><select className={select} value={part.product_id} onChange={(e)=>setMaterials((v)=>v.map((p,i)=>i===index?{...p,product_id:e.target.value}:p))}><option value="">Select company raw material</option>{options.raw_materials.map((m)=><option key={m.id} value={m.id}>{m.sku} · {m.name}</option>)}</select><input aria-label="Quantity per finished unit" placeholder="Quantity per garment" type="number" min="0.000001" step="0.000001" className={field} value={part.quantity_per_finished_unit} onChange={(e)=>setMaterials((v)=>v.map((p,i)=>i===index?{...p,quantity_per_finished_unit:e.target.value}:p))}/><button type="button" className="btn btn-ghost" onClick={()=>setMaterials((v)=>v.filter((_,i)=>i!==index))}>Remove</button></div>)}</div>
      <div className="mt-5 rounded-xl bg-slate-50 p-4 text-sm text-slate-600">Customer and sales-order association is not available until GBMS has a sales/customer module. Historical supplier/purchase references do not identify consumed materials.</div><div className="mt-5 flex justify-end"><button disabled={busy} className={button}>{busy?<LoaderCircle className="animate-spin"/>:'Save garment & generate barcode'}</button></div></form>}
      <section className="rounded-2xl border border-slate-200 bg-white shadow-sm"><div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-100 p-5"><div className="flex items-center gap-3"><span className="rounded-xl bg-sky-50 p-3 text-sky-700"><Barcode/></span><div><h2 className="font-semibold">Finished-goods catalogue</h2><p className="text-xs text-slate-500">{total} finished goods · {items.filter((x)=>x.barcode_value).length} shown on this page with barcodes</p></div></div><div className="flex flex-wrap gap-2"><input aria-label="Search SKU, name, barcode" placeholder="Search SKU, name, barcode" className={`${field} w-56`} value={search} onChange={(e)=>{setPageOffset(0);setSearch(e.target.value)}}/><select aria-label="Filter category" className="select select-bordered" value={category} onChange={(e)=>{setPageOffset(0);setCategory(e.target.value)}}><option value="">All categories</option>{options.categories.map((c)=><option key={c.id} value={c.id}>{c.name}</option>)}</select><input aria-label="Filter by size" placeholder="Size" className="input input-bordered w-24" value={size} onChange={(e)=>{setPageOffset(0);setSize(e.target.value)}}/><input aria-label="Filter by colour" placeholder="Colour" className="input input-bordered w-28" value={color} onChange={(e)=>{setPageOffset(0);setColor(e.target.value)}}/><select aria-label="Filter status" className="select select-bordered" value={status} onChange={(e)=>{setPageOffset(0);setStatus(e.target.value)}}><option>ALL</option><option>ACTIVE</option><option>INACTIVE</option></select><button className="btn btn-outline" onClick={reload}><Search size={16}/>Search</button></div></div>
      <div className="overflow-x-auto"><table className="table"><thead><tr><th>Product / variant</th><th>SKU</th><th>Price</th><th>Barcode</th><th>Generated by / at</th><th>Actions</th></tr></thead><tbody>{items.map((item)=><tr key={item.product_id}><td><strong>{item.product_name}</strong><div className="text-xs text-slate-500">{[item.design,item.size,item.color].filter(Boolean).join(' · ')||'No variant details'}</div></td><td>{item.sku}</td><td>{item.selling_price==null?'—':`PKR ${Number(item.selling_price).toFixed(2)}`}</td><td className="font-mono text-xs">{item.barcode_value||'Not generated'}</td><td className="text-xs">{item.barcode_generated_by||'Legacy / unknown'}<div className="text-slate-500">{item.barcode_generated_at?new Date(item.barcode_generated_at).toLocaleString():'—'}</div></td><td><div className="flex gap-2">{!item.barcode_value&&<button disabled={busy||!item.is_active} className="btn btn-outline btn-sm" onClick={()=>action(item.product_id,barcodeService.generate)}>Generate</button>}{item.barcode_value&&<><button disabled={busy} className="btn btn-outline btn-sm" onClick={()=>print(item.product_id)}><Printer size={14}/>Print</button><button disabled={busy} className="btn btn-ghost btn-sm" onClick={()=>showDetails(item.product_id)}>Details</button></>}</div></td></tr>)}{!items.length&&<tr><td colSpan="6" className="py-12 text-center text-slate-500">No finished goods match these filters.</td></tr>}</tbody></table></div><div className="flex items-center justify-between border-t border-slate-100 px-5 py-3 text-sm text-slate-500"><span>{total ? `${pageOffset + 1}–${Math.min(pageOffset + items.length, total)} of ${total}` : "0 products"}</span><div className="flex gap-2"><button className="btn btn-outline btn-sm" disabled={pageOffset===0} onClick={()=>setPageOffset((v)=>Math.max(0,v-100))}>Previous</button><button className="btn btn-outline btn-sm" disabled={pageOffset+100>=total} onClick={()=>setPageOffset((v)=>v+100)}>Next</button></div></div></section>
    {details&&<section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><div className="flex justify-between"><div><h2 className="font-semibold">{details.product_name} · material and purchase details</h2><p className="text-sm text-slate-500">Barcode: <span className="font-mono">{details.barcode_value}</span></p></div><div className="flex gap-2"><button className={`btn btn-outline btn-sm ${canUpdate ? "" : "hidden"}`} onClick={()=>{setDetailMaterials((details.raw_materials||[]).map((m)=>({product_id:m.product_id,quantity_per_finished_unit:m.quantity_per_finished_unit})));setEditingMaterials(!editingMaterials)}}>{editingMaterials?'Cancel':'Edit material plan'}</button><button className="btn btn-ghost btn-sm" onClick={()=>{setDetails(null);setEditingMaterials(false)}} aria-label="Close details"><X size={16}/></button></div></div>{editingMaterials?<div className="mt-4"><p className="text-xs text-slate-500">Changing a plan does not change stock or record actual consumption.</p>{detailMaterials.map((part,index)=><div className="mt-3 grid gap-3 md:grid-cols-[1fr_220px_auto]" key={index}><select className={select} value={part.product_id} onChange={(e)=>setDetailMaterials((v)=>v.map((p,i)=>i===index?{...p,product_id:e.target.value}:p))}><option value="">Select raw material</option>{options.raw_materials.map((m)=><option key={m.id} value={m.id}>{m.sku} · {m.name}</option>)}</select><input className={field} aria-label="Quantity per finished unit" type="number" min="0.000001" step="0.000001" value={part.quantity_per_finished_unit} onChange={(e)=>setDetailMaterials((v)=>v.map((p,i)=>i===index?{...p,quantity_per_finished_unit:e.target.value}:p))}/><button className="btn btn-ghost" onClick={()=>setDetailMaterials((v)=>v.filter((_,i)=>i!==index))}>Remove</button></div>)}<button className="btn btn-outline btn-sm mt-3" onClick={()=>setDetailMaterials((v)=>[...v,{product_id:'',quantity_per_finished_unit:''}])}>Add material</button><button disabled={busy} className={`${button} ml-2 mt-3`} onClick={saveMaterialPlan}>Save material plan</button></div>:<><h3 className="mt-5 text-sm font-semibold">Planned materials</h3><div className="mt-2 overflow-x-auto"><table className="table table-sm"><thead><tr><th>Raw material</th><th>Variant</th><th>Quantity per garment</th></tr></thead><tbody>{details.raw_materials?.map((m)=><tr key={m.product_id}><td>{m.name} <span className="text-xs text-slate-500">{m.sku}</span></td><td>{[m.design,m.size,m.color].filter(Boolean).join(' · ')||'—'}</td><td>{m.quantity_per_finished_unit} {m.unit}</td></tr>)}</tbody></table>{!details.raw_materials?.length&&<p className="py-3 text-sm text-slate-500">No material plan linked.</p>}</div><h3 className="mt-5 text-sm font-semibold">Supplier purchase history</h3><p className="text-xs text-slate-500">Purchase history only; it does not prove that material was consumed in this product.</p>{details.purchase_history?.length?<div className="mt-2 overflow-x-auto"><table className="table table-sm"><thead><tr><th>Material SKU</th><th>Purchase order</th><th>Supplier</th><th>Status</th><th>Ordered</th><th>Unit cost</th></tr></thead><tbody>{details.purchase_history.map((p,i)=><tr key={`${p.purchase_order_id}-${i}`}><td>{p.raw_material_sku}</td><td>{p.purchase_order_number}</td><td>{p.supplier_name}</td><td>{p.status}</td><td>{p.ordered_quantity} {p.unit}</td><td>PKR {Number(p.unit_cost).toFixed(2)}</td></tr>)}</tbody></table></div>:<p className="py-3 text-sm text-slate-500">No permitted purchase-history rows to show.</p>}</>}</section>}
    <section className="grid gap-5 lg:grid-cols-2"><article className="rounded-2xl border border-slate-200 bg-white p-5"><h2 className="font-semibold">Scan or look up a label</h2><p className="mt-1 text-sm text-slate-500">USB barcode readers work as keyboard input. Camera detection depends on browser support.</p><form className="mt-4 flex gap-2" onSubmit={(e)=>{e.preventDefault();doLookup()}}><input className={field} value={scan} onChange={(e)=>setScan(e.target.value)} placeholder="Scan or enter barcode"/><button className={button}><Search size={16}/>Look up</button></form><div className="mt-3 flex gap-2"><button className="btn btn-outline btn-sm" onClick={startCamera}><Camera size={15}/>Use camera</button><button className="btn btn-ghost btn-sm" onClick={()=>{stream.current?.getTracks().forEach((t)=>t.stop());stream.current=null;setCameraMessage('Camera stopped.')}}>Stop camera</button></div>{cameraMessage&&<p className="mt-2 text-xs text-slate-500">{cameraMessage}</p>}<video ref={video} className="mt-3 max-h-48 rounded-lg" muted playsInline/>{scanResult&&<div className="mt-3 rounded-lg bg-sky-50 p-3 text-sm"><b>{scanResult.product_name}</b><div>{scanResult.sku} · {scanResult.variant_size||'—'} · {scanResult.variant_color||'—'}</div><span className="font-mono text-xs">{scanResult.barcode_value}</span></div>}</article>
      <article className="rounded-2xl border border-slate-200 bg-white p-5"><h2 className="font-semibold">Print labels</h2><p className="mt-1 text-sm text-slate-500">Print from any row with a saved barcode. Labels show product details and price; only the unique barcode ID is encoded.</p><label className="mt-4 block max-w-52 text-sm">Copies per label<input className={`${field} mt-1`} type="number" min="1" max="200" value={copies} onChange={(e)=>setCopies(e.target.value)}/></label><p className="mt-3 text-xs text-slate-500">Generated barcodes record the authenticated user and server UTC time. Legacy codes without audit fields are shown as unknown.</p></article></section>
  </main>
}
