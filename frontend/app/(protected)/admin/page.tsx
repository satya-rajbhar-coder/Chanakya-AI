import { redirect } from "next/navigation"

import AdminPanel from "@/components/admin/AdminPanel"
import { getSession } from "@/services/session.server"

export default async function AdminPage() {
    const session = await getSession()

    if (!session.authenticated) {
        redirect("/login?reason=expired")
    }

    if (session.user?.role !== "admin") {
        redirect("/")
    }

    return <AdminPanel currentUserId={session.user.id} />
}
