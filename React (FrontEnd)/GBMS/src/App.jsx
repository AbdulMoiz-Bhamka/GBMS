// src/App.jsx
import { useEffect, useRef, useState } from 'react'
import {
  ArrowDown, ArrowRight, ArrowUpRight, BarChart3, Box, BriefcaseBusiness,
  Check, ChevronDown, CircleDollarSign, ClipboardList, Factory, FileChartColumn,
  Layers3, Menu, PackageCheck, ShieldCheck, ShoppingBag, Users, Warehouse, X,
} from 'lucide-react'
import { Navigate, Route, Routes, useNavigate } from 'react-router-dom'
import { useAuth } from './auth/useAuth'
import ProtectedRoute from './auth/ProtectedRoute'
import DashboardPage from './pages/Dashboard/Dashboard'
import './App.css'
import AdminLayout from './Components/Layout/AdminLayout'
import RoleRoute from './auth/RoleRoute'
import CompaniesPage from './pages/Companies/CompaniesPage'
import InventoryPage from './pages/Inventory/InventoryPage'
import UsersPage from './pages/Users/UsersPage'
import SuppliersPage from './pages/Suppliers/SuppliersPage'
import PurchaseOrdersPage from './pages/Purchasing/PurchaseOrdersPage'
import PasswordSecurityPage from './pages/Auth/PasswordSecurityPage'

const links = [
  ['Overview', '#home'],
  ['Capabilities', '#capabilities'],
  ['Modules', '#modules'],
  ['How it works', '#workflow'],
]

const capabilities = [
  { icon: Warehouse, title: 'Inventory, in context', text: 'See materials, finished goods and stock movement in one dependable view.', tag: 'STOCK & MATERIALS' },
  { icon: Factory, title: 'Production, connected', text: 'Follow work in progress, production stages and output across your floor.', tag: 'PLANNING & OUTPUT' },
  { icon: Users, title: 'People, organized', text: 'Keep employee, department and position information together and up to date.', tag: 'EMPLOYEE RECORDS' },
  { icon: ShoppingBag, title: 'Purchasing, clearer', text: 'Keep suppliers, procurement activity and purchasing records close at hand.', tag: 'SUPPLIERS & ORDERS' },
  { icon: BriefcaseBusiness, title: 'Customers & sales', text: 'Connect customer records with sales activity and business transactions.', tag: 'CUSTOMER RELATIONSHIPS' },
  { icon: CircleDollarSign, title: 'Finance, together', text: 'Organize financial information and transactions alongside your operations.', tag: 'FINANCIAL RECORDS' },
  { icon: Box, title: 'Assets, accounted for', text: 'Record company assets and keep track of their lifecycle over time.', tag: 'ASSET LIFECYCLE' },
  { icon: FileChartColumn, title: 'Reports that inform', text: 'Review operational activity through clear, useful business reporting.', tag: 'REPORTING & INSIGHT' },
]

const modules = [
  ['Dashboard', BarChart3], ['Employees', Users], ['Products', PackageCheck],
  ['Inventory', Warehouse], ['Purchasing', ShoppingBag], ['Production', Factory],
  ['Quality control', ShieldCheck], ['Sales', ArrowUpRight], ['Customers', BriefcaseBusiness],
  ['Finance', CircleDollarSign], ['Assets', Box], ['Reports', FileChartColumn],
]

const steps = [
  { number: '01', title: 'Bring it together', text: 'Centralize your people, products, suppliers and business records.' },
  { number: '02', title: 'Keep work moving', text: 'Coordinate purchasing, inventory, production and sales.' },
  { number: '03', title: 'See what is happening', text: 'Follow operational activity and keep teams aligned.' },
  { number: '04', title: 'Make informed decisions', text: 'Use business reports to understand performance and plan ahead.' },
]

function Brand({ inverse = false }) {
  return <a href="#home" className={`brand-mark-link${inverse ? ' brand-inverse' : ''}`} aria-label="GBMS home">
    <span className="brand-symbol" aria-hidden="true"><i /><i /><i /><i /></span>
    <span className="brand-wordmark"><strong>GBMS</strong><small>Garment Business Management System</small></span>
  </a>
}

function LoginPopover({ open, onClose }) {
  const ref = useRef(null)
  const [message, setMessage] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    if (!open) return undefined
    const handlePointer = (event) => { if (ref.current && !ref.current.contains(event.target)) onClose() }
    const handleKey = (event) => { if (event.key === 'Escape') onClose() }
    document.addEventListener('pointerdown', handlePointer)
    document.addEventListener('keydown', handleKey)
    return () => {
      document.removeEventListener('pointerdown', handlePointer)
      document.removeEventListener('keydown', handleKey)
    }
  }, [open, onClose])

  if (!open) return null
  return <section ref={ref} role="dialog" aria-modal="false" className="login-panel card bg-base-100 shadow-xl" aria-labelledby="login-title">
    <div className="card-body gap-0 p-6">
      <div className="mb-5 flex items-start justify-between">
        <div><span className="section-kicker">PRIVATE WORKSPACE</span><h2 id="login-title" className="mt-2 text-xl font-semibold tracking-tight text-[#283d4c]">Welcome back</h2><p className="mt-1 text-xs text-[#7d8b96]">Sign in with your organization account.</p></div>
        <button type="button" className="btn btn-ghost btn-square btn-sm text-[#798b98]" aria-label="Close login" onClick={onClose}><X size={18} /></button>
      </div>
      <form onSubmit={async (event) => {
        event.preventDefault()
        setMessage('')
        setIsSubmitting(true)
        const formData = new FormData(event.currentTarget)
        try {
          await login({ username: formData.get('username'), password: formData.get('password') })
          onClose()
          navigate('/dashboard')
        } catch (error) {
          setMessage(error.message || 'Unable to sign in. Please try again.')
        } finally {
          setIsSubmitting(false)
        }
      }}>
        <label htmlFor="gbms-username" className="mb-1.5 block text-xs font-semibold text-[#435464]">Username</label>
        <input id="gbms-username" name="username" autoComplete="username" required maxLength={80} className="input input-bordered w-full bg-white text-sm" placeholder="Enter your username" />
        <label htmlFor="gbms-password" className="mb-1.5 mt-4 block text-xs font-semibold text-[#435464]">Password</label>
        <input id="gbms-password" name="password" type="password" autoComplete="current-password" required maxLength={1024} className="input input-bordered w-full bg-white text-sm" placeholder="Enter your password" />
        <button type="submit" disabled={isSubmitting} className="btn btn-primary mt-5 w-full justify-between px-4">{isSubmitting ? 'Signing in…' : 'Login'} <ArrowRight size={17} /></button>
        {message && <p className="alert mt-3 rounded-lg bg-[#edf6fb] px-3 py-2 text-xs text-[#386f92]" role="status">{message}</p>}
        <p className="mt-4 text-center text-[11px] leading-5 text-[#8997a2]">Workspace access is managed by your organization administrator.</p>
      </form>
    </div>
  </section>
}

function Navbar({ onLogin }) {
  const [menuOpen, setMenuOpen] = useState(false)
  const openLogin = () => { setMenuOpen(false); onLogin() }
  return <header className="site-header sticky top-0 z-40">
    <nav className="navbar wrap-shell min-h-[76px] px-0" aria-label="Main navigation">
      <div className="navbar-start"><Brand /></div>
      <div className="navbar-center hidden lg:flex">
        <ul className="menu menu-horizontal nav-menu gap-1 px-1">
          {links.map(([label, href], index) => <li key={href}><a className={index === 0 ? 'nav-link nav-link-active' : 'nav-link'} href={href}>{label}</a></li>)}
        </ul>
      </div>
      <div className="navbar-end gap-4">
        <div className="hidden items-center gap-2.5 border-r border-[#e6ebef] pr-5 sm:flex"><span className="access-dot" /><span className="text-[10px] font-semibold uppercase tracking-[.11em] text-[#8796a1]">Authorized access</span></div>
        <button type="button" className="btn btn-primary nav-login" onClick={openLogin}>Workspace login <ArrowUpRight size={16} /></button>
        <button type="button" className="btn btn-square btn-ghost mobile-menu-toggle lg:hidden" aria-label={menuOpen ? 'Close navigation menu' : 'Open navigation menu'} aria-expanded={menuOpen} onClick={() => setMenuOpen((value) => !value)}>{menuOpen ? <X size={21} /> : <Menu size={21} />}</button>
      </div>
      {menuOpen && <div className="mobile-nav dropdown-content bg-base-100 shadow-xl lg:hidden">
        <ul className="menu w-full p-2">{links.map(([label, href]) => <li key={href}><a href={href} onClick={() => setMenuOpen(false)}>{label}<ArrowUpRight size={15} /></a></li>)}</ul>
        <div className="p-2 pt-0"><button type="button" className="btn btn-primary w-full justify-between" onClick={openLogin}>Workspace login <ArrowUpRight size={16} /></button></div>
      </div>}
    </nav>
  </header>
}

function DashboardPreview() {
  const bars = [36, 49, 43, 62, 53, 77, 60, 88, 67, 96, 74, 86]
  return <div className="dashboard-preview card bg-white">
    <div className="dash-topbar"><div className="flex items-center gap-2"><span className="dash-glyph">G</span><strong className="text-[10px] font-extrabold tracking-[.1em] text-[#345c74]">GBMS</strong><span className="mx-2 h-4 w-px bg-[#e8edf0]" /><span className="text-[9px] text-[#7d8c98]">Workspace overview <ChevronDown size={11} className="ml-1 inline" /></span></div><span className="dash-user">AM</span></div>
    <div className="dash-layout">
      <aside className="dash-sidebar"><span className="dash-side-active"><BarChart3 size={12} />Overview</span><span><Warehouse size={12} />Inventory</span><span><Layers3 size={12} />Production</span><span><Users size={12} />Employees</span><span><ArrowUpRight size={12} />Sales</span><span className="mt-auto"><ClipboardList size={12} />Reports</span></aside>
      <div className="dash-main">
        <div className="flex items-start justify-between"><div><span className="dash-date">MONDAY, OCTOBER 4, 2026</span><h3 className="mt-1 text-[15px] font-semibold tracking-tight text-[#293e4d]">Business overview</h3><p className="mt-1 text-[8px] text-[#85939f]">Your operations at a glance.</p></div><span className="dash-filter">This month <ChevronDown size={10} /></span></div>
        <div className="dash-stat-grid">
          <div className="dash-stat"><span>Monthly revenue</span><strong>$84,260</strong><small><b>↗ 12.8%</b> vs last month</small></div>
          <div className="dash-stat"><span>In production</span><strong>24 <em>orders</em></strong><small><b>↗ 4.2%</b> this week</small></div>
          <div className="dash-stat"><span>Inventory health</span><strong>92.4<em>%</em></strong><small><b className="steady">● On track</b></small></div>
        </div>
        <div className="dash-bottom-row">
          <div className="dash-chart"><div className="flex items-start justify-between"><div><strong>Revenue overview</strong><small>Monthly performance</small></div><span className="chart-key"><i /> Revenue</span></div><div className="chart-plot"><div className="plot-lines"><i>$100k</i><i>$75k</i><i>$50k</i><i>$25k</i></div><div className="plot-bars">{bars.map((height, index) => <i key={index} style={{ height: `${height}%` }} />)}</div></div><div className="plot-months"><span>May</span><span>Jun</span><span>Jul</span><span>Aug</span><span>Sep</span><span>Oct</span></div></div>
          <div className="dash-activity"><div className="flex items-start justify-between"><div><strong>Recent activity</strong><small>Across your business</small></div><span className="text-xs text-[#a2adb4]">···</span></div><div className="activity-item"><span className="activity-icon activity-green"><Check size={11} /></span><div><b>Production completed</b><small>Order #PR-2048 · 12 min ago</small></div></div><div className="activity-item"><span className="activity-icon activity-amber"><Box size={11} /></span><div><b>Stock replenished</b><small>Organic cotton · 48 min ago</small></div></div><div className="activity-item"><span className="activity-icon activity-blue"><ArrowUpRight size={11} /></span><div><b>New sales order</b><small>Northline Apparel · 1 hr ago</small></div></div></div>
        </div>
        <div className="mt-3 flex items-center gap-2 text-[7px] text-[#80919d]"><span className="access-dot" /> All systems operational <span className="ml-auto text-[#a1abb2]">Illustrative data</span></div>
      </div>
    </div>
  </div>
}

function HeroSection({ onLogin }) {
  return <section id="home" className="hero-section relative overflow-hidden">
    <div className="hero-orbit hero-orbit-a" /><div className="hero-orbit hero-orbit-b" />
    <div className="wrap-shell hero-grid relative z-10">
      <div className="hero-copy">
        <div className="badge badge-outline hero-badge"><span className="access-dot" /> GARMENT BUSINESS MANAGEMENT SYSTEM</div>
        <h1>Every part of your garment business, <span>working together.</span></h1>
        <p className="hero-description">GBMS brings your people, inventory, production and business operations into one clear, connected workspace.</p>
        <div className="mt-8 flex flex-wrap items-center gap-3"><button type="button" className="btn btn-primary btn-lg hero-cta" onClick={onLogin}>Login to your workspace <ArrowRight size={17} /></button><a className="btn btn-ghost btn-lg hero-secondary" href="#capabilities">Explore capabilities <ArrowDown size={15} /></a></div>
        <div className="hero-proof"><span><Check size={14} /> Made for garment operations</span><i /><span>One connected workspace</span></div>
      </div>
      <div className="hero-preview-wrap"><div className="preview-caption"><span className="access-dot" /> AN OPERATIONAL OVERVIEW</div><DashboardPreview /><div className="preview-note"><span className="preview-note-icon"><Layers3 size={17} /></span><span><b>Connected by design</b><small>Every operation, in context</small></span><ArrowUpRight size={16} className="ml-auto text-[#718999]" /></div></div>
    </div>
    <a href="#capabilities" className="hero-scroll"><span /> Scroll to explore</a>
  </section>
}

function SectionIntro({ label, title, description, light = false }) {
  return <div className={`section-intro${light ? ' section-intro-light' : ''}`}><span className="section-kicker">{label}</span><h2>{title}</h2>{description && <p>{description}</p>}</div>
}

function CapabilitiesSection() {
  return <section className="section-shell capabilities-section" id="capabilities"><div className="wrap-shell">
    <SectionIntro label="BUILT AROUND THE WORK" title={<>A clearer way to run <span>the day to day.</span></>} description="Practical tools for the teams, materials and decisions behind garment production." />
    <div className="capability-grid">{capabilities.map(({ icon: Icon, title, text, tag }, index) => <article className="card capability-card" key={title}><div className="card-body"><div className={`capability-icon tone-${index % 4}`}><Icon size={20} strokeWidth={1.7} /></div><span className="capability-tag">{tag}</span><h3>{title}</h3><p>{text}</p><span className="capability-number">0{index + 1}</span></div></article>)}</div>
    <div className="capability-note"><span className="note-check"><Check size={15} /></span><p><strong>One shared view for your team.</strong> Keep information connected as work moves from planning through production and delivery.</p></div>
  </div></section>
}

function ModulesSection() {
  return <section className="modules-section" id="modules"><div className="wrap-shell modules-grid"><div className="modules-copy"><span className="section-kicker section-kicker-light">ONE CONNECTED PLATFORM</span><h2>One system.<br /><span>Every operation.</span></h2><p>From the first material order to the finished sale, keep the moving parts of your business in sync.</p><a href="#workflow" className="modules-link">See how it works <ArrowRight size={16} /></a><div className="module-shared"><span /> Shared business information</div></div><div className="card module-card"><div className="module-card-head"><div><span className="module-eyebrow">YOUR BUSINESS, CONNECTED</span><h3>Explore the modules</h3></div><span className="badge badge-outline module-count">12 AREAS</span></div><div className="module-grid">{modules.map(([label, Icon], index) => <div className="module-item" key={label}><span className="module-number">{String(index + 1).padStart(2, '0')}</span><Icon size={15} strokeWidth={1.7} /><span>{label}</span><ArrowUpRight size={13} className="module-item-arrow" /></div>)}</div><div className="module-card-foot"><span className="access-dot" /> One workspace. A more connected operation.</div></div></div></section>
}

function WorkflowSection() {
  return <section className="section-shell workflow-section" id="workflow"><div className="wrap-shell"><SectionIntro label="HOW GBMS HELPS" title={<>From daily work to <span>business clarity.</span></>} description="Bring the work together, then keep a useful view of how everything is moving." /><div className="workflow-grid">{steps.map(({ number, title, text }) => <article className="workflow-step" key={number}><div className="workflow-step-head"><span>{number}</span><i /></div><h3>{title}</h3><p>{text}</p></article>)}</div><div className="workflow-summary"><div className="summary-icon"><BarChart3 size={19} /></div><p><strong>A more complete picture of the business.</strong> Connected operational information helps your team stay coordinated as work moves forward.</p><div className="summary-line" /></div></div></section>
}

function CTASection({ onLogin }) {
  return <section id="about" className="cta-shell"><div className="wrap-shell cta-card"><div className="cta-orbit" /><div className="cta-content"><span className="section-kicker section-kicker-light">YOUR BUSINESS, IN SYNC</span><h2>Bring the moving parts <span>together.</span></h2><p>Access your GBMS workspace and manage garment business operations from one central place.</p><button className="btn btn-neutral cta-button" onClick={onLogin}>Login to GBMS <ArrowRight size={17} /></button></div><div className="cta-side-label"><span /> GARMENT BUSINESS<br />MANAGEMENT SYSTEM</div></div></section>
}

function Footer({ onLogin }) {
  return <footer className="site-footer"><div className="wrap-shell"><div className="footer-grid"><div className="footer-about"><Brand inverse /><p>A connected workspace for the people, products and processes that keep garment businesses moving.</p></div><div className="footer-column"><h3>Explore</h3><a href="#home">Overview</a><a href="#capabilities">Capabilities</a><a href="#modules">Modules</a><a href="#workflow">How it works</a></div><div className="footer-column"><h3>Workspace</h3><button onClick={onLogin}>Login</button><a href="#about">Security</a><a href="#about">Privacy</a></div><div className="footer-column"><h3>Contact</h3><p>Contact details are available<br />through your administrator.</p></div></div><div className="footer-bottom"><span>© 2026 GBMS. All rights reserved, Designed by Abdul Moiz.</span><span><i /> Designed By Abdul Moiz</span></div></div></footer>
}

function LandingPage() {
  const [loginOpen, setLoginOpen] = useState(false)
  const openLogin = () => setLoginOpen(true)
  const closeLogin = () => setLoginOpen(false)
  return <><Navbar onLogin={openLogin} /><main><HeroSection onLogin={openLogin} /><CapabilitiesSection /><ModulesSection /><WorkflowSection /><CTASection onLogin={openLogin} /></main><Footer onLogin={openLogin} /><div className="global-login-anchor"><LoginPopover open={loginOpen} onClose={closeLogin} /></div></>
}

function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route element={<ProtectedRoute />}>
        <Route path="/change-password" element={<PasswordSecurityPage forced />} />
        <Route element={<AdminLayout />}>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route element={<RoleRoute allowedRoles={['SUPER_ADMIN']} />}>
            <Route path="/companies" element={<CompaniesPage />} />
          </Route>
          <Route element={<RoleRoute requiredPermission="users.view" requiresCompany />}>
            <Route path="/users" element={<UsersPage />} />
          </Route>
          <Route element={<RoleRoute requiredPermission="inventory.view" requiresCompany />}>
            <Route path="/inventory" element={<InventoryPage />} />
          </Route>
          <Route element={<RoleRoute requiredPermission="suppliers.view" requiresCompany />}>
            <Route path="/suppliers" element={<SuppliersPage />} />
          </Route>
          <Route element={<RoleRoute requiredPermission="purchasing.view" requiresCompany />}>
            <Route path="/purchase-orders" element={<PurchaseOrdersPage />} />
          </Route>
          <Route path="/security" element={<PasswordSecurityPage />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App
