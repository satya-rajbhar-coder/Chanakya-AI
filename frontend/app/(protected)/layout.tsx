import { redirect } from "next/navigation";

import { AppSidebar } from "@/components/app-sidebar";
import { WorkspaceProvider } from "@/components/workspace-provider";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";

import { getSession } from "@/services/session";

interface ProtectedLayoutProps {
    children: React.ReactNode;
}

export default async function ProtectedLayout({
    children,
}: ProtectedLayoutProps) {
    const session = await getSession();

    if (!session.authenticated) {
        redirect("/login?reason=expired");
    }

    return (
        <WorkspaceProvider>
            <SidebarProvider>
                <AppSidebar user={session.user} />

                <SidebarInset className="h-svh overflow-hidden">
                    {children}
                </SidebarInset>
            </SidebarProvider>
        </WorkspaceProvider>
    );
}
