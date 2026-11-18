import { redirect } from "next/navigation";

import { AppSidebar } from "@/components/app-sidebar";
import { DialogProvider } from "@/components/ui/dialog-provider";
import { ToastProvider } from "@/components/ui/toast-provider";
import { WorkspaceProvider } from "@/components/workspace-provider";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";

import { getSession } from "@/services/session.server";

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
        <DialogProvider>
            <WorkspaceProvider>
                <SidebarProvider>
                    <ToastProvider>
                        <AppSidebar user={session.user} />

                        <SidebarInset className="h-svh overflow-hidden">
                            {children}
                        </SidebarInset>
                    </ToastProvider>
                </SidebarProvider>
            </WorkspaceProvider>
        </DialogProvider>
    );
}
