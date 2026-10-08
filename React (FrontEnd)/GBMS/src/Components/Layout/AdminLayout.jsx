// src/Components/Layout/AdminLayout.jsx

import { Outlet } from "react-router-dom";
import Sidebar from "./Sidebar";
import Topbar from './Topbar'


export default function AdminLayout() {
    return (
        <div className="min-h-screen bg-[#f7f9fa]">
            <Sidebar />

            <div>
                <Topbar />
            </div>

            <main>
                <Outlet />
            </main>

        </div>

    )
}