"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import type { FormEvent, ReactNode } from "react"
import { Loader2, Trash2, AlertTriangle, UserX, Database, FileText, Users, Shield, Plus } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import { useWorkspace } from "@/components/workspace-provider"
import { useDialogs } from "@/components/ui/dialog-provider"
import { TooltipProvider } from "@/components/ui/tooltip"

import type { UserRole } from "@/services/auth"
import {
    AdminUser,
    AvailableDatabase,
    Client,
    ROLE_HIERARCHY,
    ROLE_LABELS,
    createAdminUser,
    deleteAdminUser,
    deactivateAdminUser,
    getAvailableDatabases,
    listAdminClients,
    listAdminUsers,
    setUserAssignments,
    updateAdminUser,
} from "@/services/admin"
import {
    ACCEPTED_FILES,
    DocumentResponse,
    deleteDocument,
    getAllDocuments,
    uploadDocument,
} from "@/services/documents"
import { getApiErrorMessage } from "@/services/error"
import { mapWithConcurrency } from "@/lib/utils"


const Message = ({ error, success }: { error?: string | null; success?: string | null }) => (
    <>
        {error && (
            <p role="alert" className="text-sm text-destructive">
                {error}
            </p>
        )}
        {success && <p className="text-sm text-emerald-600 dark:text-emerald-400">{success}</p>}
    </>
)

const Field = ({ label, children, required = false }: { label: string; children: ReactNode; required?: boolean }) => (
    <label className="flex flex-col gap-1.5 text-sm">
        <span className="text-muted-foreground flex items-center gap-1">
            {label}
            {required && <span className="text-destructive">*</span>}
        </span>
        {children}
    </label>
)

const Section = ({ title, description, children, icon }: { title: string; description: string; children: ReactNode; icon?: ReactNode }) => (
    <Card>
        <CardHeader>
            <div className="flex items-center gap-2">
                {icon}
                <div>
                    <CardTitle className="text-base">{title}</CardTitle>
                    <CardDescription>{description}</CardDescription>
                </div>
            </div>
        </CardHeader>
        <CardContent className="flex flex-col gap-6">{children}</CardContent>
    </Card>
)

const checkboxClass = "size-4 shrink-0 cursor-pointer accent-primary"

const tableHeadClass =
    "whitespace-nowrap px-3 py-2.5 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground"

const tableCellClass = "whitespace-nowrap px-3 py-2.5 text-sm"

const clientLabel = (c: Client) => `${c.name} · ${c.client_identifier}`

interface ClientPickerProps {
    clients: Client[]
    selected: string[]
    onChange: (ids: string[]) => void
    disabled?: boolean
}

const ClientPicker = ({ clients, selected, onChange, disabled }: ClientPickerProps) => {
    if (clients.length === 0) {
        return <p className="text-sm text-muted-foreground">No clients available.</p>
    }

    const toggle = (id: string) =>
        onChange(selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id])

    return (
        <div className="flex max-h-44 flex-col gap-0.5 overflow-y-auto rounded-md border p-2">
            {clients.map((c) => (
                <label
                    key={c.id}
                    className="flex cursor-pointer items-center gap-2.5 rounded px-2 py-1.5 text-sm"
                >
                    <input
                        type="checkbox"
                        className={checkboxClass}
                        checked={selected.includes(c.id)}
                        onChange={() => toggle(c.id)}
                        disabled={disabled}
                    />
                    {clientLabel(c)}
                </label>
            ))}
        </div>
    )
}

interface DatabaseSelectorProps {
    databases: AvailableDatabase[]
    selected: string | null
    onChange: (name: string | null) => void
    disabled?: boolean
    placeholder?: string
}

const DatabaseSelector = ({ databases, selected, onChange, disabled, placeholder = "Select database" }: DatabaseSelectorProps) => {
    const availableDatabases = databases.filter(db => !db.is_assigned)
    
    if (availableDatabases.length === 0) {
        return (
            <div className="flex items-center gap-2">
                <Select value={selected ?? ""} onValueChange={onChange} disabled={disabled || true}>
                    <SelectTrigger className="w-full">
                        <SelectValue placeholder={placeholder} />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="" disabled>No unassigned databases available</SelectItem>
                    </SelectContent>
                </Select>
                <span className="text-xs text-destructive">No unassigned databases available</span>
            </div>
        )
    }

    return (
        <Select value={selected ?? ""} onValueChange={(v) => onChange(v || null)} disabled={disabled}>
            <SelectTrigger className="w-full">
                <SelectValue placeholder={placeholder} />
            </SelectTrigger>
            <SelectContent>
                {availableDatabases.map((db) => (
                    <SelectItem key={db.name} value={db.name}>
                        {db.name}
                    </SelectItem>
                ))}
            </SelectContent>
        </Select>
    )
}

const UserRow = ({ user, clients, isSelf, onChanged, onDelete }: {
    user: AdminUser
    clients: Client[]
    isSelf: boolean
    onChanged: (user: AdminUser) => void
    onDelete: () => void
}) => {
    const [assigned, setAssigned] = useState<string[]>(user.client_ids)
    const [password, setPassword] = useState("")
    const [busy, setBusy] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [success, setSuccess] = useState<string | null>(null)
    const { confirm } = useDialogs()

    const dirty =
        assigned.length !== user.client_ids.length ||
        assigned.some((id) => !user.client_ids.includes(id))

    const run = async (action: () => Promise<AdminUser>, done: string) => {
        setBusy(true)
        setError(null)
        setSuccess(null)
        try {
            const updated = await action()
            onChanged(updated)
            setAssigned(updated.client_ids)
            setSuccess(done)
        } catch (err) {
            setError(getApiErrorMessage(err))
        } finally {
            setBusy(false)
        }
    }

    const saveAssignments = () =>
        run(() => setUserAssignments(user.id, assigned), "Assignments saved")

    const toggleActive = async () => {
        if (user.is_active) {
            const approved = await confirm({
                title: "Deactivate user?",
                description: `"${user.name}" will be deactivated and lose access. They can be reactivated later.`,
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
        await run(() => updateAdminUser(user.id, { password }), "Password updated")
        setPassword("")
    }

    const handleDelete = async () => {
        const approved = await confirm({
            title: "Delete user permanently?",
            description: `This will permanently delete "${user.name}" and all their data. This action cannot be undone.`,
            confirmLabel: "Delete Permanently",
            cancelLabel: "Cancel",
            destructive: true,
        })

        if (!approved) {
            return
        }

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

    return (
        <tr className="border-t align-top">
            <td className="px-3 py-3">
                <p className="text-sm font-medium">{user.name}</p>
                <p className="text-xs text-muted-foreground">{user.email}</p>
                <Badge
                    variant={user.role === "admin" ? "default" : "secondary"}
                    className="mt-1.5"
                    title={`Level ${user.hierarchy_level ?? ROLE_HIERARCHY[user.role]}`}
                >
                    {ROLE_LABELS[user.role] || user.role}
                    {user.ward_no && <span className="ml-1 text-xs opacity-70">· {user.ward_no}</span>}
                    {user.assembly_no && <span className="ml-1 text-xs opacity-70">· {user.assembly_no}</span>}
                    {user.parliamentary_constituency && (
                        <span className="ml-1 text-xs opacity-70">· {user.parliamentary_constituency}</span>
                    )}
                </Badge>
            </td>
            <td className="min-w-64 px-3 py-3">
                {user.role === "admin" ? (
                    <p className="text-xs text-muted-foreground">Admins can access all clients.</p>
                ) : (
                    <div className="flex flex-col gap-2">
                        <ClientPicker
                            clients={clients}
                            selected={assigned}
                            onChange={setAssigned}
                            disabled={busy}
                        />
                        <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            onClick={saveAssignments}
                            disabled={busy || !dirty}
                            className="w-fit"
                        >
                            Save assignments
                        </Button>
                    </div>
                )}
            </td>
            <td className="min-w-80 px-3 py-3">
                <div className="flex flex-col gap-2">
                    <div className="flex gap-2">
                        <Input
                            type="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            placeholder="New password"
                            autoComplete="new-password"
                            disabled={busy}
                        />
                        <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            onClick={resetPassword}
                            disabled={busy || !password}
                        >
                            Set
                        </Button>
                    </div>
                    {!isSelf && (
                        <Button
                            type="button"
                            size="sm"
                            variant={user.is_active ? "destructive" : "outline"}
                            onClick={toggleActive}
                            disabled={busy}
                            className="w-fit"
                        >
                            {user.is_active ? "Deactivate" : "Activate"}
                        </Button>
                    )}
                    {!isSelf && user.role !== "admin" && (
                        <div className="border-t pt-2">
                            <Button
                                type="button"
                                size="sm"
                                variant="ghost"
                                className="text-destructive w-fit"
                                onClick={handleDelete}
                                disabled={busy}
                            >
                                <UserX className="h-3.5 w-3.5 mr-1" />
                                Delete User
                            </Button>
                        </div>
                    )}
                    <Message error={error} success={success} />
                </div>
            </td>
        </tr>
    )
}

const UsersSection = ({
    users,
    clients,
    documents,
    databases,
    currentUserId,
    onRefreshUsers,
    onRefreshDocuments,
    onUserChanged,
}: {
    users: AdminUser[]
    clients: Client[]
    documents: DocumentResponse[]
    databases: AvailableDatabase[]
    currentUserId: string
    onRefreshUsers: () => Promise<void>
    onRefreshDocuments: () => Promise<void>
    onUserChanged: (user: AdminUser) => void
}) => {
    const [name, setName] = useState("")
    const [email, setEmail] = useState("")
    const [password, setPassword] = useState("")
    const [role, setRole] = useState<UserRole>("user")
    const [partyName, setPartyName] = useState("")
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

        // Build client_ids from selected database
        let clientIds: string[] = []
        if (selectedDatabase) {
            // Check if there's already a client for this database
            const existingClient = clients.find(c => c.database_name === selectedDatabase)
            if (existingClient) {
                clientIds = [existingClient.id]
            } else {
                // We'll create a client with this database in the backend
                // For now, pass the database name and let the backend handle it
                // The backend createAdminUser will need to be updated to accept database_name
                // For now, we'll just pass the database as a client_id placeholder
                // and the backend will need to map it
                clientIds = [] // Will be handled by backend
            }
        }

        setSaving(true)
        try {
            await createAdminUser({
                name: name.trim(),
                email: email.trim(),
                password,
                role,
                party_name: partyName.trim() || undefined,
                ward_no: wardNo.trim() ? Number(wardNo.trim()) : undefined,
                assembly_no: assemblyNo.trim() || undefined,
                parliamentary_constituency: parliamentaryConstituency.trim() || undefined,
                client_ids: clientIds,
                // Pass database_name for backend to create client if needed
                database_name: selectedDatabase || undefined,
            } as any)
            setSuccess(`User ${email.trim()} created`)
            setName("")
            setEmail("")
            setPassword("")
            setRole("user")
            setPartyName("")
            setWardNo("")
            setAssemblyNo("")
            setParliamentaryConstituency("")
            setSelectedDatabase(null)
            await onRefreshUsers()
        } catch (err) {
            setError(getApiErrorMessage(err))
        } finally {
            setSaving(false)
        }
    }

    // Role-specific required fields
    const requiresWard = role === "karyakarta" || role === "corporator"
    const requiresAssembly = role === "aamdar"
    const requiresParliamentary = role === "khasdar"

    return (
        <Section
            title="User Management"
            description="Create and manage user accounts with database/client assignments and document access."
            icon={<Users className="h-5 w-5" />}
        >
            <div className="grid gap-6">
                {/* Create User Form */}
                <form onSubmit={handleSubmit} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
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
                    <Field label="Party name">
                        <Input
                            value={partyName}
                            onChange={(e) => setPartyName(e.target.value)}
                            placeholder="e.g., Bharatiya Janata Party"
                            disabled={saving}
                        />
                    </Field>
                    {requiresWard && (
                        <Field label="Ward number" required>
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
                        <Field label="Assembly number" required>
                            <Input
                                value={assemblyNo}
                                onChange={(e) => setAssemblyNo(e.target.value)}
                                placeholder="e.g., Assembly 12"
                                disabled={saving}
                            />
                        </Field>
                    )}
                    {requiresParliamentary && (
                        <Field label="Parliamentary constituency" required>
                            <Input
                                value={parliamentaryConstituency}
                                onChange={(e) => setParliamentaryConstituency(e.target.value)}
                                placeholder="e.g., PC 5"
                                disabled={saving}
                            />
                        </Field>
                    )}
                    <Field label="Database" required>
                        <DatabaseSelector
                            databases={databases}
                            selected={selectedDatabase}
                            onChange={setSelectedDatabase}
                            disabled={saving}
                            placeholder="Select database for this user"
                        />
                    </Field>
                    <div className="flex flex-col gap-1.5 text-sm lg:col-span-2">
                        <span className="text-muted-foreground">Additional Clients (optional)</span>
                        <ClientPicker
                            clients={clients}
                            selected={[]}
                            onChange={() => {}}
                            disabled={true}
                        />
                        <p className="text-xs text-muted-foreground">
                            Primary database is selected above. Additional clients can be assigned after creation.
                        </p>
                    </div>
                    <div className="flex flex-col justify-end gap-3">
                        <Message error={error} success={success} />
                        <Button type="submit" disabled={saving} className="w-fit">
                            {saving ? "Creating…" : "Create User"}
                        </Button>
                    </div>
                </form>

                {/* Users Table */}
                <Card>
                    <CardHeader>
                        <CardTitle className="text-base">Users</CardTitle>
                        <CardDescription>Manage user accounts, client access, and document assignments.</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="overflow-x-auto rounded-md border">
                            <table className="w-full">
                                <thead className="bg-muted/50">
                                    <tr>
                                        <th className={tableHeadClass}>User</th>
                                        <th className={tableHeadClass}>Clients</th>
                                        <th className={tableHeadClass}>Account</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {users.length === 0 ? (
                                        <tr>
                                            <td colSpan={3} className="px-3 py-6 text-center text-sm text-muted-foreground">
                                                No users yet.
                                            </td>
                                        </tr>
                                    ) : (
                                        users.map((user) => (
                                            <UserRow
                                                key={user.id}
                                                user={user}
                                                clients={clients}
                                                isSelf={user.id === currentUserId}
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

                {/* Document Upload & Assignment */}
                <DocumentsSection
                    documents={documents}
                    users={users}
                    onRefresh={onRefreshDocuments}
                />
            </div>
        </Section>
    )
}

/* ------------------------------------------------------------------ */
/* Documents Section (integrated into Users tab)                      */
/* ------------------------------------------------------------------ */

const DocumentsSection = ({
    documents,
    users,
    onRefresh,
}: {
    documents: DocumentResponse[]
    users: AdminUser[]
    onRefresh: () => Promise<void>
}) => {
    const [userIds, setUserIds] = useState<string[]>([])
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

        if (userIds.length === 0) {
            setError("Choose at least one user")
            return
        }
        if (files.length === 0) {
            setError("Choose at least one file")
            return
        }

        const errors: string[] = []
        let done = 0

        await mapWithConcurrency(files, 3, async (file) => {
            try {
                await uploadDocument(file, userIds)
            } catch (err) {
                errors.push(`${file.name}: ${getApiErrorMessage(err)}`)
            } finally {
                done += 1
                setUploadingName(`${done}/${files.length}`)
            }
        })

        setUploadingName(null)
        setFiles([])
        if (fileRef.current) fileRef.current.value = ""

        const ok = files.length - errors.length
        if (ok > 0) setSuccess(`Uploaded ${ok} ${ok === 1 ? "document" : "documents"}`)
        if (errors.length > 0) setError(errors.join(" "))

        await onRefresh()
    }

    const handleDelete = async (doc: DocumentResponse) => {
        const approved = await confirm({
            title: "Delete document?",
            description: `"${doc.filename}" will be removed from all assigned users.`,
            confirmLabel: "Delete",
            destructive: true,
        })

        if (!approved) {
            return
        }

        setError(null)
        setSuccess(null)
        try {
            await deleteDocument(doc.id)
            setSuccess(`Deleted ${doc.filename}`)
            await onRefresh()
        } catch (err) {
            setError(getApiErrorMessage(err))
        }
    }

    return (
        <Section
            title="Document Management"
            description="Upload knowledge-base files and assign them to users."
            icon={<FileText className="h-5 w-5" />}
        >
            <form onSubmit={handleSubmit} className="grid gap-4 lg:grid-cols-2">
                <Field label="Assign to users" required>
                    <div className="flex max-h-44 flex-col gap-0.5 overflow-y-auto rounded-md border p-2">
                        {users.map((user) => (
                            <label
                                key={user.id}
                                className="flex cursor-pointer items-center gap-2.5 rounded px-2 py-1.5 text-sm"
                            >
                                <input
                                    type="checkbox"
                                    className={checkboxClass}
                                    checked={userIds.includes(user.id)}
                                    onChange={() => setUserIds(prev =>
                                        prev.includes(user.id)
                                            ? prev.filter(id => id !== user.id)
                                            : [...prev, user.id]
                                    )}
                                    disabled={uploading}
                                />
                                {user.name}
                                <span className="truncate text-muted-foreground">({user.email})</span>
                            </label>
                        ))}
                    </div>
                </Field>

                <div className="flex flex-col gap-4">
                    <Field label="Files (PDF, TXT, Markdown)" required>
                        <input
                            ref={fileRef}
                            type="file"
                            accept={ACCEPTED_FILES}
                            multiple
                            onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
                            disabled={uploading}
                            className="w-full rounded-md border border-input bg-transparent p-2 text-sm file:mr-3 file:rounded-md file:border-0 file:bg-secondary file:px-3 file:py-1.5 file:text-sm file:font-medium"
                        />
                    </Field>

                    <div className="flex flex-col gap-3">
                        {uploading && (
                            <p className="flex items-center gap-2 text-sm text-muted-foreground">
                                <Loader2 className="size-4" />
                                Uploading {uploadingName}… large PDFs can take a minute.
                            </p>
                        )}
                        <Message error={error} success={success} />
                        <Button type="submit" disabled={uploading} className="w-fit">
                            {uploading ? "Uploading…" : "Upload"}
                        </Button>
                    </div>
                </div>
            </form>

            <div className="overflow-x-auto rounded-md border">
                <table className="w-full">
                    <thead className="bg-muted/50">
                        <tr>
                            <th className={tableHeadClass}>File</th>
                            <th className={tableHeadClass}>Assigned users</th>
                            <th className={tableHeadClass}>Chunks</th>
                            <th className={tableHeadClass}>Uploaded</th>
                            <th className={tableHeadClass} />
                        </tr>
                    </thead>
                    <tbody>
                        {documents.length === 0 ? (
                            <tr>
                                <td colSpan={5} className="px-3 py-6 text-center text-sm text-muted-foreground">
                                    No documents yet.
                                </td>
                            </tr>
                        ) : (
                            documents.map((doc) => {
                                const assignedUserNames =
                                    doc.assigned_user_ids
                                        .map((id: string) => {
                                            const user = users.find(u => u.id === id)
                                            return user ? user.name : id
                                        })
                                        .join(", ") || "—"

                                return (
                                    <tr key={doc.id} className="border-t">
                                        <td className="max-w-xs truncate px-3 py-2.5 text-sm" title={doc.filename}>
                                            {doc.filename}
                                        </td>
                                        <td className={tableCellClass}>
                                            {assignedUserNames}
                                        </td>
                                        <td className={tableCellClass}>{doc.chunk_count}</td>
                                        <td className={tableCellClass}>
                                            {new Date(doc.created_at).toLocaleString()}
                                        </td>
                                        <td className="px-3 py-2.5 text-right">
                                            <button
                                                type="button"
                                                onClick={() => handleDelete(doc)}
                                                className="rounded p-1.5 text-muted-foreground hover:text-destructive"
                                                aria-label={`Delete ${doc.filename}`}
                                            >
                                                <Trash2 className="size-4" />
                                            </button>
                                        </td>
                                    </tr>
                                )
                            })
                        )}
                    </tbody>
                </table>
            </div>
        </Section>
    )
}

/* ------------------------------------------------------------------ */

const AdminPanel = ({ currentUserId }: { currentUserId: string }) => {
    const { refreshDocuments: refreshSidebarDocuments } = useWorkspace()

    const [clients, setClients] = useState<Client[]>([])
    const [users, setUsers] = useState<AdminUser[]>([])
    const [documents, setDocuments] = useState<DocumentResponse[]>([])
    const [databases, setDatabases] = useState<AvailableDatabase[]>([])
    const [loading, setLoading] = useState(true)
    const [loadError, setLoadError] = useState<string | null>(null)

    const loadClients = useCallback(async () => {
        setClients(await listAdminClients())
    }, [])

    const loadUsers = useCallback(async () => {
        setUsers(await listAdminUsers())
    }, [])

    const loadDocuments = useCallback(async () => {
        setDocuments(await getAllDocuments())
        await refreshSidebarDocuments()
    }, [refreshSidebarDocuments])

    const loadDatabases = useCallback(async () => {
        setDatabases(await getAvailableDatabases())
    }, [])

    const handleUserChanged = (updated: AdminUser) =>
        setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)))

    useEffect(() => {
        Promise.all([
            listAdminClients(),
            listAdminUsers(),
            getAllDocuments(),
            getAvailableDatabases(),
        ])
            .then(([clientList, userList, documentList, databaseList]) => {
                setClients(clientList)
                setUsers(userList)
                setDocuments(documentList)
                setDatabases(databaseList)
            })
            .catch((err) => setLoadError(getApiErrorMessage(err)))
            .finally(() => setLoading(false))
    }, [])

    const refreshAll = useCallback(async () => {
        await Promise.all([loadClients(), loadUsers(), loadDocuments(), loadDatabases()])
    }, [loadClients, loadUsers, loadDocuments, loadDatabases])

    return (
        <TooltipProvider>
            <div className="min-h-0 flex-1 overflow-y-auto bg-transparent">
                <div className="mx-auto w-full max-w-6xl p-6 md:p-8">
                    <div className="mb-6">
                        <h1 className="text-xl font-semibold tracking-tight">Administration</h1>
                        <p className="mt-1 text-sm text-muted-foreground">
                            Manage users, database assignments and document access.
                        </p>
                    </div>

                    {loading ? (
                        <div className="flex items-center gap-2 py-16 text-sm text-muted-foreground">
                            <Loader2 className="size-4" />
                            Loading
                        </div>
                    ) : (
                        <>
                            <Message error={loadError} />

                            <Tabs defaultValue="users" className="flex flex-col gap-4">
                                <TabsList className="w-fit">
                                    <TabsTrigger value="users">
                                        <Users className="h-4 w-4 mr-2" />
                                        Users
                                    </TabsTrigger>
                                </TabsList>

                                <TabsContent value="users">
                                    <UsersSection
                                        users={users}
                                        clients={clients}
                                        documents={documents}
                                        databases={databases}
                                        currentUserId={currentUserId}
                                        onRefreshUsers={loadUsers}
                                        onRefreshDocuments={loadDocuments}
                                        onUserChanged={handleUserChanged}
                                    />
                                </TabsContent>
                            </Tabs>
                        </>
                    )}
                </div>
            </div>
        </TooltipProvider>
    )
}

export default AdminPanel