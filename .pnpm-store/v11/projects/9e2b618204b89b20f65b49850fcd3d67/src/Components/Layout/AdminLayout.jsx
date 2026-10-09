// src/Components/Layout/AdminLayout.jsx

import { Outlet } from "react-router-dom";
import Sidebar from "./Sidebar";
import Topbar from './Topbar'


export default function AdminLayout() {
    return (
        <div className="flex min-h-screen bg-[#f7f9fa]">
            <Sidebar />

            <div className="min-w-0 flex-1">
                <Topbar />

                <main className="p-6 lg:p-8">
                    <Outlet />
                </main>
            </div>
        </div>

    )
}