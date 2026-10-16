import { redirect } from "next/navigation"

// Public self-registration is disabled; accounts are created by admins.
export default function Register() {
    redirect("/login")
}
