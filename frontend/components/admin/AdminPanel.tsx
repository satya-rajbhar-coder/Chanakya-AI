"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import type { FormEvent, ReactNode } from "react"
import {
    Loader2,
    Trash2,
    AlertTriangle,
    UserX,
    Database,
    FileText,
    Users,
    Shield,
    Plus,
    RefreshCw,
    Upload,
    Eye,
    EyeOff,
    Building2,
    MapPin,
    Phone,
    Tag,
    Target,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import {
    Card,
    CardContent,
    CardDescription,
    CardFooter,
    CardHeader,
    CardTitle,
} from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import { TooltipProvider } from "@/components/ui/tooltip"
import { useDialogs } from "@/components/ui/dialog-provider"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Separator } from "@/components/ui/separator"
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area"

import type { UserRole } from "@/services/auth"
import {
    AdminUser,
    AvailableDatabase,
    ROLE_HIERARCHY,
    ROLE_LABELS,
    createAdminUser,
    deleteAdminUser,
    deactivateAdminUser,
    getAvailableDatabases,
    listAdminUsers,
    assignUserToDatabase,
    updateAdminUser,
} from "@/services/admin"
import {
    ACCEPTED_FILES,
    DocumentResponse,
    assignDocumentUsers,
    deleteDocument,
    getAllDocuments,
    uploadDocument,
} from "@/services/documents"
import { getApiErrorMessage } from "@/services/error"
import { cn } from "@/lib/utils"

const ROLE_CONFIGS: Record<UserRole, { color: string; label: string }> = {
    admin: { color: "bg-primary text-primary-foreground", label: "Administrator" },
    khasdar: { color: "bg-blue-500 text-blue-50", label: "Khasdar" },
    aamdar: { color: "bg-purple-500 text-purple-50", label: "Aamdar" },
    corporator: { color: "bg-orange-500 text-orange-50", label: "Corporator" },
    karyakarta: { color: "bg-green-500 text-green-50", label: "Karyakarta" },
}

const Message = ({ error, success }: { error?: string | null; success?: string | null }) => (
    <>
        {error && (
            <div role="alert" className="rounded-lg border border-destructive/50 bg-destructive/50 p-4 text-sm text-destructive flex items-start gap-3">
                <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" /> {error}
            </div>
        )}
        {success && (
            <div className="rounded-lg border border-emerald-50/50 bg-emerald-50/50 p-4 text-sm text-emerald-700 flex items-start gap-3">
                <FileText className="h-4 w-4 mt-0.5 shrink-0" /> {success}
            </div>
        )}
    </>
)

const Field = ({ label, children, required = false }: { label: string; children: ReactNode; required?: boolean }) => (
    <div className="flex flex-col gap-1.5">
        <label className="flex items-center gap-1 text-sm font-medium text-foreground">
            {label}
            {required && <span className="ml-0.5 text-destructive text-sm">*</span>}
        </label>
        {children}
    </div>
)

const Section = ({ title, description, children, icon }: { title: string; description: string; children: ReactNode; icon?: ReactNode }) => (
    <Card className="overflow-hidden border">
        <CardHeader>
            <div className="flex items-center gap-3">
                <div className="rounded-lg bg-muted p-2">
                    {icon}
                </div>
                <div>
                    <CardTitle className="text-sm font-semibold">{title}</CardTitle>
                    <CardDescription className="text-xs text-muted-foreground">{description}</CardDescription>
                </div>
            </div>
        </CardHeader>
        <CardContent className="pt-0">{children}</CardContent>
    </Card>
)

/* ======================================================================== */
/* User Row Component                                                       */
/* ======================================================================== */

const UserRow = ({ user, databases, onChanged, onDelete }: {
    user: AdminUser
    databases: AvailableDatabase[]
    onChanged: (user: AdminUser) => void
    onDelete: () => void
}) => {
    const [database, setDatabase] = useState<string | null>(null)
    const [password, setPassword] = useState("")
    const [showPassword, setShowPassword] = useState(false)
    const [busy, setBusy] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [success, setSuccess] = useState<string | null>(null)
    const { confirm } = useDialogs()

    const run = async (action: () => Promise<AdminUser>, done: string) => {
        setBusy(true)
        setError(null)
        setSuccess(null)
        try {
            const updated = await action()
            onChanged(updated)
            setSuccess(done)
        } catch (err) {
            setError(getApiErrorMessage(err))
        } finally {
            setBusy(false)
        }
    }

    const assignDatabase = async () => {
        if (!database) return
        run(
            () => assignUserToDatabase(user.id, database),
            "Database assigned"
        )
    }

    const toggleActive = async () => {
        if (user.is_active) {
            const approved = await confirm({
                title: "Deactivate user?",
                description: `"${user.name}" will be deactivated and lose access.`,
                confirmLabel: "Deactivate",
                destructive: true,
            })
            if (!approved) return
            run(
                () => deactivateAdminUser(user.id),
                "User deactivated"
            )
        } else {
            run(
                () => updateAdminUser(user.id, { is_active: true }),
                "User activated"
            )
        }
    }

    const resetPassword = async () => {
        if (!password) return
        await run(() => updateAdminUser(user.id, { password }), "Password updated")
        setPassword("")
        setShowPassword(false)
    }

    const handleDelete = async () => {
        const approved = await confirm({
            title: "Delete user permanently?",
            description: `This will permanently delete "${user.name}" and all their data.`,
            confirmLabel: "Delete Permanently",
            cancelLabel: "Cancel",
            destructive: true,
        })

        if (!approved) return

        setBusy(true)
        setError(null)
        setSuccess(null)
        try {
            await deleteAdminUser(user.id, true)
            setSuccess(`User "${user.name}" deleted`)
            onDelete()
        } catch (err) {
            setError(getApiErrorMessage(err))
        } finally {
            setBusy(false)
        }
    }

    const roleConfig = ROLE_CONFIGS[user.role as keyof typeof ROLE_CONFIGS] ?? ROLE_CONFIGS.karyakarta

    return (
        <tr className="border-t align-top hover:bg-muted/50 transition-colors group">
            <td className="px-4 py-4 text-sm">
                <div className="flex flex-col gap-1">
                    <div className="flex items-center gap-2">
                        <div className={`h-8 w-8 rounded-full flex items-center justify-center text-sm font-medium ${roleConfig.color}`}>
                            {user.name?.charAt(0).toUpperCase() || 'U'}
                        </div>
                        <div className="flex flex-col gap-0.5">
                            <p className="text-sm font-medium text-foreground">{user.name}</p>
                            <p className="text-xs text-muted-foreground">{user.email}</p>
                        </div>
                    </div>
                    <Badge
                        variant="secondary"
                        className={cn("mt-1", roleConfig.color)}
                        title={`Level ${user.hierarchy_level ?? ROLE_HIERARCHY[user.role]}`}
                    >
                        {ROLE_LABELS[user.role] || user.role}
                    </Badge>
                    <div className="flex items-center gap-1 mt-1 text-xs opacity-70">
                        {user.corporation && (
                            <span className="flex items-center gap-1">
                                <Building2 className="h-3 w-3" /> {user.corporation}
                            </span>
                        )}
                        {user.ward_no && (
                            <span className="flex items-center gap-1">
                                <Tag className="h-3 w-3" /> Ward {user.ward_no}
                            </span>
                        )}
                        {user.assembly_no && (
                            <span className="flex items-center gap-1">
                                <Target className="h-3 w-3" /> Assembly {user.assembly_no}
                            </span>
                        )}
                    </div>
                </div>
            </td>
            <td className="px-4 py-4 text-sm">
                {user.role === "admin" ? (
                    <p className="text-xs text-muted-foreground">Admin - all access</p>
                ) : (
                    <div className="flex flex-col gap-2">
                        <Select
                            value={database ?? ""}
                            onValueChange={(v) => setDatabase(v || null)}
                            disabled={busy}
                        >
                            <SelectTrigger className="w-full">
                                <SelectValue placeholder="Select database" />
                            </SelectTrigger>
                            <SelectContent>
                                {databases.filter(db => !db.is_assigned).map((db) => (
                                    <SelectItem key={db.name} value={db.name}>
                                        {db.name}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                        <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            onClick={assignDatabase}
                            disabled={busy || !database}
                            className="w-full"
                        >
                            Assign
                        </Button>
                    </div>
                )}
            </td>
            <td className="px-4 py-4 text-sm">
                <div className="flex flex-col gap-2">
                    <div className="flex gap-2">
                        <Input
                            type={showPassword ? "text" : "password"}
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            placeholder="New password"
                            autoComplete="new-password"
                            disabled={busy}
                            className="text-sm flex-1"
                        />
                        <Button
                            type="button"
                            size="icon"
                            variant="ghost"
                            onClick={() => setShowPassword(!showPassword)}
                            disabled={busy}
                            aria-label={showPassword ? "Hide password" : "Show password"}
                        >
                            {showPassword ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
                        </Button>
                        <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            onClick={resetPassword}
                            disabled={busy || !password}
                            className="w-fit"
                        >
                            Set
                        </Button>
                    </div>
                    <Button
                        type="button"
                        size="sm"
                        variant={user.is_active ? "destructive" : "outline"}
                        onClick={toggleActive}
                        disabled={busy}
                        className="w-full"
                    >
                        {user.is_active ? "Deactivate" : "Activate"}
                    </Button>
                    {user.role !== "admin" && (
                        <div className="border-t pt-2">
                            <Button
                                type="button"
                                size="sm"
                                variant="ghost"
                                className="text-destructive w-full"
                                onClick={handleDelete}
                                disabled={busy}
                            >
                                <UserX className="h-3 w-3 mr-1" />
                                Delete
                            </Button>
                        </div>
                    )}
                    {error && <p className="text-xs text-destructive">{error}</p>}
                    {success && <p className="text-xs text-emerald-600">{success}</p>}
                </div>
            </td>
        </tr>
    )
}

/* ======================================================================== */
/* Users Tab Section                                                        */
/* ======================================================================== */

const UsersTabSection = ({
    users,
    databases,
    documents,
    onRefreshUsers,
    onUserChanged,
}: {
    users: AdminUser[]
    databases: AvailableDatabase[]
    documents: DocumentResponse[]
    onRefreshUsers: () => Promise<void>
    onUserChanged: (user: AdminUser) => void
}) => {
    const [open, setOpen] = useState(false)
    const [name, setName] = useState("")
    const [email, setEmail] = useState("")
    const [password, setPassword] = useState("")
    const [role, setRole] = useState<UserRole>("karyakarta")
    const [partyName, setPartyName] = useState("")
    const [corporation, setCorporation] = useState("")
    const [wardNo, setWardNo] = useState("")
    const [assemblyNo, setAssemblyNo] = useState("")
    const [parliamentaryConstituency, setParliamentaryConstituency] = useState("")
    const [selectedDatabase, setSelectedDatabase] = useState<string | null>(null)
    const [saving, setSaving] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [success, setSuccess] = useState<string | null>(null)

    const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault()
        setError(null)
        setSuccess(null)

        if (!name.trim() || !email.trim() || !password) {
            setError("Name, email and password are required")
            return
        }

        const requiresWard = role === "karyakarta" || role === "corporator"
        const requiresAssembly = role === "aamdar"
        const requiresParliamentary = role === "khasdar"

        if (requiresWard && !wardNo.trim()) {
            setError("Ward number is required for this role")
            return
        }
        if (requiresAssembly && !assemblyNo.trim()) {
            setError("Assembly number is required for this role")
            return
        }
        if (requiresParliamentary && !parliamentaryConstituency.trim()) {
            setError("Parliamentary constituency is required for this role")
            return
        }

        setSaving(true)
        try {
            await createAdminUser({
                name: name.trim(),
                email: email.trim(),
                password,
                role,
                party_name: partyName.trim() || undefined,
                corporation: corporation.trim() || undefined,
                ward_no: wardNo.trim() ? Number(wardNo.trim()) : undefined,
                assembly_no: assemblyNo.trim() || undefined,
                parliamentary_constituency: parliamentaryConstituency.trim() || undefined,
                database_name: selectedDatabase || undefined,
            })
            setSuccess(`User ${email.trim()} created`)
            setName("")
            setEmail("")
            setPassword("")
            setRole("karyakarta")
            setPartyName("")
            setCorporation("")
            setWardNo("")
            setAssemblyNo("")
            setParliamentaryConstituency("")
            setSelectedDatabase(null)
            await onRefreshUsers()
            setTimeout(() => setOpen(false), 1500)
        } catch (err) {
            setError(getApiErrorMessage(err))
        } finally {
            setSaving(false)
        }
    }

    const requiresWard = role === "karyakarta" || role === "corporator"
    const requiresAssembly = role === "aamdar"
    const requiresParliamentary = role === "khasdar"

    return (
        <>
            <Dialog open={open} onOpenChange={setOpen}>
                <DialogContent className="sm:max-w-[480px]">
                    <DialogHeader>
                        <DialogTitle>Create New User</DialogTitle>
                        <DialogDescription>
                            Fill in user details. Role-specific fields appear automatically.
                        </DialogDescription>
                    </DialogHeader>
                    <form onSubmit={handleSubmit} className="grid gap-3 sm:grid-cols-2 py-4">
                        <Field label="Name" required>
                            <Input value={name} onChange={(e) => setName(e.target.value)} disabled={saving} />
                        </Field>
                        <Field label="Email" required>
                            <Input
                                type="email"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                autoComplete="off"
                                disabled={saving}
                            />
                        </Field>
                        <Field label="Password" required>
                            <Input
                                type="password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                autoComplete="new-password"
                                disabled={saving}
                            />
                        </Field>
                        <Field label="Role" required>
                            <Select
                                value={role}
                                onValueChange={(value) => setRole(value as UserRole)}
                                disabled={saving}
                            >
                                <SelectTrigger className="w-full">
                                    <SelectValue placeholder="Select role" />
                                </SelectTrigger>
                                <SelectContent>
                                    {Object.entries(ROLE_HIERARCHY).map(([key]) => (
                                        <SelectItem key={key} value={key}>
                                            {ROLE_LABELS[key]}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </Field>
                        <Field label="Party Name">
                            <Input
                                value={partyName}
                                onChange={(e) => setPartyName(e.target.value)}
                                placeholder="e.g., Bharatiya Janata Party"
                                disabled={saving}
                            />
                        </Field>
                        <Field label="Corporation / ULB">
                            <Input
                                value={corporation}
                                onChange={(e) => setCorporation(e.target.value)}
                                placeholder="e.g., KDMC, AMC, TMC"
                                disabled={saving}
                            />
                        </Field>
                        {requiresWard && (
                            <Field label="Ward Number" required>
                                <Input
                                    type="number"
                                    value={wardNo}
                                    onChange={(e) => setWardNo(e.target.value)}
                                    placeholder="e.g., 5"
                                    disabled={saving}
                                />
                            </Field>
                        )}
                        {requiresAssembly && (
                            <Field label="Assembly Number" required>
                                <Input
                                    value={assemblyNo}
                                    onChange={(e) => setAssemblyNo(e.target.value)}
                                    placeholder="e.g., Assembly 12"
                                    disabled={saving}
                                />
                            </Field>
                        )}
                        {requiresParliamentary && (
                            <Field label="Parliamentary Constituency" required>
                                <Input
                                    value={parliamentaryConstituency}
                                    onChange={(e) => setParliamentaryConstituency(e.target.value)}
                                    placeholder="e.g., PC 5"
                                    disabled={saving}
                                />
                            </Field>
                        )}
                        <Field label="Database" required>
                            <Select
                                value={selectedDatabase ?? ""}
                                onValueChange={(v) => setSelectedDatabase(v || null)}
                                disabled={saving}
                            >
                                <SelectTrigger className="w-full">
                                    <SelectValue placeholder="Select database" />
                                </SelectTrigger>
                                <SelectContent>
                                    {databases.filter(db => !db.is_assigned).map((db) => (
                                        <SelectItem key={db.name} value={db.name}>
                                            {db.name}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </Field>
                        <div className="flex flex-col justify-end gap-2 sm:col-span-2">
                            <Message error={error} success={success} />
                            <Button type="submit" disabled={saving} className="w-full">
                                {saving ? "Creating…" : "Create User"}
                            </Button>
                        </div>
                    </form>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setOpen(false)} className="w-fit">
                            Cancel
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            <Section
                title="User Management"
                description="Create and manage user accounts with database allotment."
                icon={<Users className="h-4 w-4" />}
            >
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                    {/* Users Table */}
                    <Card className="lg:col-span-3 overflow-hidden">
                        <CardHeader className="flex flex-row items-center justify-between">
                            <div>
                                <CardTitle className="text-sm font-semibold">Users</CardTitle>
                                <CardDescription className="text-xs text-muted-foreground">Manage user accounts and database assignments.</CardDescription>
                            </div>
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => setOpen(true)}
                                disabled={saving}
                            >
                                <Plus className="h-3 w-3 mr-1" /> Add User
                            </Button>
                        </CardHeader>
                        <CardContent>
                            <div className="overflow-x-auto rounded-md border">
                                <table className="w-full text-sm">
                                    <thead>
                                        <tr>
                                            <th className="whitespace-nowrap px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground bg-muted/50">User</th>
                                            <th className="whitespace-nowrap px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground bg-muted/50">Database</th>
                                            <th className="whitespace-nowrap px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground bg-muted/50">Account</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {users.length === 0 ? (
                                            <tr>
                                                <td colSpan={3} className="px-4 py-8 text-center text-sm text-muted-foreground">
                                                    No users yet.
                                                </td>
                                            </tr>
                                        ) : (
                                            users.map((user) => (
                                                <UserRow
                                                    key={user.id}
                                                    user={user}
                                                    databases={databases}
                                                    onChanged={onUserChanged}
                                                    onDelete={onRefreshUsers}
                                                />
                                            ))
                                        )}
                                    </tbody>
                                </table>
                            </div>
                        </CardContent>
                    </Card>
                </div>
            </Section>
        </>
    )
}

/* ======================================================================== */
/* Documents Tab Section - Only Ingestion                                   */
/* ======================================================================== */

const DocumentsTabSection = ({
    documents,
    onRefreshDocuments,
}: {
    documents: DocumentResponse[]
    onRefreshDocuments: () => Promise<void>
}) => {
    const [files, setFiles] = useState<File[]>([])
    const [uploadingName, setUploadingName] = useState<string | null>(null)
    const [error, setError] = useState<string | null>(null)
    const [success, setSuccess] = useState<string | null>(null)
    const fileRef = useRef<HTMLInputElement>(null)
    const { confirm } = useDialogs()

    const uploading = uploadingName !== null

    const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault()
        setError(null)
        setSuccess(null)

        if (files.length === 0) {
            setError("Choose at least one file")
            return
        }

        const errors: string[] = []
        let done = 0

        for (const file of files) {
            try {
                await uploadDocument(file, [])
            } catch (err) {
                errors.push(`${file.name}: ${getApiErrorMessage(err)}`)
            } finally {
                done += 1
                setUploadingName(`${done}/${files.length}`)
            }
        }

        setUploadingName(null)
        setFiles([])
        if (fileRef.current) fileRef.current.value = ""

        const ok = files.length - errors.length
        if (ok > 0) setSuccess(`Uploaded ${ok} ${ok === 1 ? "document" : "documents"}`)
        if (errors.length > 0) setError(errors.join(" "))

        await onRefreshDocuments()
    }

    const handleDelete = async (doc: DocumentResponse) => {
        const approved = await confirm({
            title: "Delete document?",
            description: `"${doc.filename}" will be removed permanently.`,
            confirmLabel: "Delete",
            destructive: true,
        })

        if (!approved) return

        setError(null)
        setSuccess(null)
        try {
            await deleteDocument(doc.id)
            setSuccess(`Document "${doc.filename}" deleted`)
            await onRefreshDocuments()
        } catch (err) {
            setError(getApiErrorMessage(err))
        }
    }

    return (
        <Section
            title="Document Ingestion"
            description="Upload documents for vector search and RAG."
            icon={<Upload className="h-4 w-4" />}
        >
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {/* Upload Area */}
                <Card className="lg:col-span-2 border-dashed hover:border-primary/50 transition-colors">
                    <CardHeader className="flex flex-col items-center justify-center py-6">
                        <div className="flex items-center justify-center w-10 h-10 rounded-md bg-primary/10 text-primary mb-2">
                            <Upload className="h-5 w-5" />
                        </div>
                        <CardTitle className="text-sm font-semibold">Upload Documents</CardTitle>
                        <CardDescription className="text-xs text-muted-foreground">
                            Supported: .pdf, .txt, .md
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <form onSubmit={handleSubmit} className="grid gap-3">
                            <Field label="Files" required>
                                <div className="flex flex-col gap-2">
                                    <Input
                                        type="file"
                                        ref={fileRef}
                                        multiple
                                        accept={ACCEPTED_FILES}
                                        onChange={(e) => {
                                            const newFiles = Array.from(e.target.files || [])
                                            setFiles((prev) => [...prev, ...newFiles])
                                        }}
                                        disabled={uploading}
                                        className="text-sm"
                                    />
                                    {files.length > 0 && (
                                        <div className="flex flex-wrap gap-1">
                                            {files.map((f, i) => (
                                                <Badge key={i} variant="secondary" className="gap-1 text-xs">
                                                    {f.name}
                                                    <button
                                                        type="button"
                                                        onClick={() => setFiles((prev) => prev.filter((_, idx) => idx !== i))}
                                                        className="hover:bg-muted p-1"
                                                    >
                                                        ×
                                                    </button>
                                                </Badge>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            </Field>
                            <div className="flex flex-col justify-end gap-2">
                                <Message error={error} success={success} />
                                <Button type="submit" disabled={uploading} className="w-full">
                                    {uploading ? `Uploading ${uploadingName}…` : "Upload Documents"}
                                </Button>
                            </div>
                        </form>
                    </CardContent>
                </Card>

                {/* Documents List */}
                <Card className="lg:col-span-3 overflow-hidden">
                    <CardHeader className="flex flex-row items-center justify-between">
                        <div>
                            <CardTitle className="text-sm font-semibold">Documents</CardTitle>
                            <CardDescription className="text-xs text-muted-foreground">Manage uploaded documents.</CardDescription>
                        </div>
                    </CardHeader>
                    <CardContent>
                        <div className="overflow-x-auto rounded-md border">
                            <table className="w-full text-sm">
                                <thead>
                                    <tr>
                                        <th className="whitespace-nowrap px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground bg-muted/50">Document</th>
                                        <th className="whitespace-nowrap px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground bg-muted/50">Size</th>
                                        <th className="whitespace-nowrap px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground bg-muted/50">Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {documents.length === 0 ? (
                                        <tr>
                                            <td colSpan={3} className="px-4 py-8 text-center text-sm text-muted-foreground">
                                                No documents yet.
                                            </td>
                                        </tr>
                                    ) : (
                                        documents.map((doc) => (
                                            <tr key={doc.id} className="border-t">
                                                <td className="px-4 py-3 text-sm">
                                                    <div className="flex items-center gap-2">
                                                        <FileText className="h-3 w-3 text-muted-foreground" />
                                                        <div className="flex flex-col gap-0">
                                                            <p className="text-sm font-medium text-foreground">{doc.filename}</p>
                                                            <p className="text-xs text-muted-foreground">{doc.content_type}</p>
                                                        </div>
                                                    </div>
                                                </td>
                                                <td className="px-4 py-3 text-sm">
                                                    <span className="text-xs text-muted-foreground">
                                                        {(doc.size_bytes / 1024).toFixed(1)} KB
                                                    </span>
                                                </td>
                                                <td className="px-4 py-3 text-sm">
                                                    <Button
                                                        type="button"
                                                        size="sm"
                                                        variant="ghost"
                                                        className="text-destructive"
                                                        onClick={() => handleDelete(doc)}
                                                    >
                                                        <Trash2 className="h-3 w-3" />
                                                    </Button>
                                                </td>
                                            </tr>
                                        ))
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </CardContent>
                </Card>
            </div>
        </Section>
    )
}

/* ======================================================================== */
/* Main Admin Panel                                                         */
/* ======================================================================== */

export const AdminPanel = () => {
    const [users, setUsers] = useState<AdminUser[]>([])
    const [databases, setDatabases] = useState<AvailableDatabase[]>([])
    const [documents, setDocuments] = useState<DocumentResponse[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    const fetchUsers = useCallback(async () => {
        try {
            const data = await listAdminUsers()
            setUsers(data)
        } catch (err) {
            setError(getApiErrorMessage(err))
        }
    }, [])

    const fetchDatabases = useCallback(async () => {
        try {
            const data = await getAvailableDatabases()
            setDatabases(data)
        } catch (err) {
            setError(getApiErrorMessage(err))
        }
    }, [])

    const fetchDocuments = useCallback(async () => {
        try {
            const data = await getAllDocuments()
            setDocuments(data)
        } catch (err) {
            setError(getApiErrorMessage(err))
        }
    }, [])

    const refreshAll = useCallback(async () => {
        setLoading(true)
        setError(null)
        await Promise.all([fetchUsers(), fetchDatabases(), fetchDocuments()])
        setLoading(false)
    }, [fetchUsers, fetchDatabases, fetchDocuments])

    useEffect(() => {
        refreshAll()
    }, [refreshAll])

    const handleUserChanged = useCallback((updatedUser: AdminUser) => {
        setUsers((prev) => prev.map((u) => (u.id === updatedUser.id ? updatedUser : u)))
    }, [])

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <Loader2 className="h-6 w-6 animate-spin text-primary" />
            </div>
        )
    }

    if (error) {
        return (
            <div className="flex flex-col items-center justify-center h-64 text-center">
                <AlertTriangle className="h-8 w-8 text-destructive mb-2" />
                <h3 className="text-sm font-medium text-foreground">Failed to load admin panel</h3>
                <p className="text-xs text-muted-foreground mt-1">{error}</p>
                <Button onClick={refreshAll} className="mt-3" variant="outline">
                    <RefreshCw className="h-3 w-3 mr-1" />
                    Retry
                </Button>
            </div>
        )
    }

    return (
        <TooltipProvider>
            <ScrollArea className="h-full w-full">
                <div className="space-y-5 p-5 max-w-6xl mx-auto">
                    <div className="flex items-center justify-between">
                        <div>
                            <h1 className="text-lg font-bold text-foreground">Admin Panel</h1>
                            <p className="text-xs text-muted-foreground">
                                Manage users, database assignments, and document ingestion.
                            </p>
                        </div>
                        <Badge variant="outline" className="text-xs">
                            {users.length} users · {databases.length} databases · {documents.length} documents
                        </Badge>
                    </div>

                    <Separator />

                    <Tabs defaultValue="users" className="space-y-3">
                        <TabsList>
                            <TabsTrigger value="users">
                                <Users className="h-3 w-3 mr-1.5" />
                                Users
                            </TabsTrigger>
                            <TabsTrigger value="documents">
                                <Upload className="h-3 w-3 mr-1.5" />
                                Documents
                            </TabsTrigger>
                        </TabsList>

                        <TabsContent value="users">
                            <UsersTabSection
                                users={users}
                                databases={databases}
                                documents={documents}
                                onRefreshUsers={fetchUsers}
                                onUserChanged={handleUserChanged}
                            />
                        </TabsContent>

                        <TabsContent value="documents">
                            <DocumentsTabSection
                                documents={documents}
                                onRefreshDocuments={fetchDocuments}
                            />
                        </TabsContent>
                    </Tabs>
                </div>
                <ScrollBar />
            </ScrollArea>
        </TooltipProvider>
    )
}