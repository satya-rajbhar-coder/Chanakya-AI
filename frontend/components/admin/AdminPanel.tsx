"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import type { FormEvent, ReactNode } from "react"
import { Loader2, Trash2, X } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useWorkspace } from "@/components/workspace-provider"
import { useDialogs } from "@/components/ui/dialog-provider"
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from "@/components/ui/tooltip"

import {
    AdminUser,
    Client,
    createAdminUser,
    createClient,
    deleteClient,
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
import {
    adminListHistory,
    deleteHistory,
    type AdminHistoryItem,
} from "@/services/analysis"


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

const Field = ({ label, children }: { label: string; children: ReactNode }) => (
    <label className="flex flex-col gap-1.5 text-sm">
        <span className="text-muted-foreground">{label}</span>
        {children}
    </label>
)

const Section = ({ title, description, children }: {
    title: string
    description: string
    children: ReactNode
}) => (
    <Card>
        <CardHeader>
            <CardTitle className="text-base">{title}</CardTitle>
            <CardDescription>{description}</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-6">{children}</CardContent>
    </Card>
)

const checkboxClass = "size-4 shrink-0 cursor-pointer accent-primary"

const tableHeadClass =
    "whitespace-nowrap px-3 py-2.5 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground"

const tableCellClass = "whitespace-nowrap px-3 py-2.5 text-sm"


const clientLabel = (c: Client) => `${c.code} · ${c.name}`

interface ClientPickerProps {
    clients: Client[]
    selected: string[]
    onChange: (ids: string[]) => void
    disabled?: boolean
}

const ClientPicker = ({ clients, selected, onChange, disabled }: ClientPickerProps) => {
    if (clients.length === 0) {
        return <p className="text-sm text-muted-foreground">No clients yet.</p>
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
                    {c.client_identifier && (
                        <span className="text-muted-foreground">({c.client_identifier})</span>
                    )}
                </label>
            ))}
        </div>
    )
}


const ClientsSection = ({ clients, onCreated }: {
    clients: Client[]
    onCreated: () => Promise<void>
}) => {
    const [code, setCode] = useState("")
    const [name, setName] = useState("")
    const [databaseName, setDatabaseName] = useState("")
    const [clientIdentifier, setClientIdentifier] = useState("")
    const [description, setDescription] = useState("")
    const [saving, setSaving] = useState(false)
    const [busy, setBusy] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [success, setSuccess] = useState<string | null>(null)
    const { confirm } = useDialogs()

    const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault()
        setError(null)
        setSuccess(null)

        if (!code.trim() || !name.trim() || !databaseName.trim() || !clientIdentifier.trim()) {
            setError("Code, name, database name and client identifier are required")
            return
        }

        setSaving(true)
        try {
            await createClient({
                code: code.trim(),
                name: name.trim(),
                database_name: databaseName.trim(),
                client_identifier: clientIdentifier.trim(),
                description: description.trim() || undefined,
            })
            setSuccess(`Client "${name.trim()}" created`)
            setCode("")
            setName("")
            setDatabaseName("")
            setClientIdentifier("")
            setDescription("")
            await onCreated()
        } catch (err) {
            setError(getApiErrorMessage(err))
        } finally {
            setSaving(false)
        }
    }

    const handleDeleteClient = async (clientId: string, clientName: string) => {
        const approved = await confirm({
            title: "Delete client?",
            description: `"${clientName}" and its database assignment will be permanently removed. This action cannot be undone.`,
            confirmLabel: "Delete",
            destructive: true,
        })

        if (!approved) {
            return
        }

        setBusy(true)
        setError(null)
        setSuccess(null)
        try {
            await deleteClient(clientId)
            setSuccess(`Client deleted`)
            await onCreated()
        } catch (err) {
            setError(getApiErrorMessage(err))
        } finally {
            setBusy(false)
        }
    }

    return (
        <Section
            title="Clients"
            description="Client databases available for assignment."
        >
            <form onSubmit={handleSubmit} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                <Field label="Code *">
                    <Input value={code} onChange={(e) => setCode(e.target.value)} disabled={saving} />
                </Field>
                <Field label="Name *">
                    <Input value={name} onChange={(e) => setName(e.target.value)} disabled={saving} />
                </Field>
                <Field label="Database name *">
                    <Input
                        value={databaseName}
                        onChange={(e) => setDatabaseName(e.target.value)}
                        disabled={saving}
                    />
                </Field>
                <Field label="Client identifier *">
                    <Input
                        value={clientIdentifier}
                        onChange={(e) => setClientIdentifier(e.target.value)}
                        placeholder="e.g., client147"
                        disabled={saving}
                    />
                </Field>
                <Field label="Description">
                    <Input
                        value={description}
                        onChange={(e) => setDescription(e.target.value)}
                        disabled={saving}
                    />
                </Field>
                <div className="flex flex-col justify-end gap-3">
                    <Message error={error} success={success} />
                    <Button type="submit" disabled={saving} className="w-fit">
                        {saving ? "Creating…" : "Create client"}
                    </Button>
                </div>
            </form>

            <div className="overflow-x-auto rounded-md border">
                <table className="w-full">
                    <thead className="bg-muted/50">
                        <tr>
                            <th className={tableHeadClass}>Code</th>
                            <th className={tableHeadClass}>Name</th>
                            <th className={tableHeadClass}>Client ID</th>
                            <th className={tableHeadClass}>Database</th>
                            <th className={tableHeadClass}>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {clients.length === 0 ? (
                            <tr>
                                <td colSpan={6} className="px-3 py-6 text-center text-sm text-muted-foreground">
                                    No clients yet.
                                </td>
                            </tr>
                        ) : (
                            clients.map((c) => (
                                <tr key={c.id} className="border-t">
                                    <td className={`${tableCellClass} font-mono`}>{c.code}</td>
                                    <td className={tableCellClass}>{c.name}</td>
                                    <td className={`${tableCellClass} font-mono`}>{c.client_identifier}</td>
                                    <td className={`${tableCellClass} font-mono`}>{c.database_name}</td>
                                    <td className={tableCellClass}>
                                        <Badge variant={c.is_active ? "success" : "secondary"}>
                                            {c.is_active ? "Active" : "Inactive"}
                                        </Badge>
                                    </td>
                                    <td className={tableCellClass}>
                                        <Tooltip>
                                            <TooltipTrigger asChild>
                                                <Button
                                                    variant="ghost"
                                                    size="icon"
                                                    onClick={() => handleDeleteClient(c.id, c.name)}
                                                    disabled={busy}
                                                    className="text-destructive"
                                                    aria-label={`Delete ${c.name}`}
                                                >
                                                    <Trash2 className="h-3.5 w-3.5" />
                                                </Button>
                                            </TooltipTrigger>
                                            <TooltipContent side="left">Delete client</TooltipContent>
                                        </Tooltip>
                                    </td>
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
            </div>
        </Section>
    )
}


const UserRow = ({ user, clients, isSelf, onChanged }: {
    user: AdminUser
    clients: Client[]
    isSelf: boolean
    onChanged: (user: AdminUser) => void
}) => {
    const [assigned, setAssigned] = useState<string[]>(user.client_ids)
    const [password, setPassword] = useState("")
    const [busy, setBusy] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [success, setSuccess] = useState<string | null>(null)

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

    const toggleActive = () =>
        run(
            () => updateAdminUser(user.id, { is_active: !user.is_active }),
            user.is_active ? "User deactivated" : "User activated"
        )

    const resetPassword = async () => {
        await run(() => updateAdminUser(user.id, { password }), "Password updated")
        setPassword("")
    }

    return (
        <tr className="border-t align-top">
            <td className="px-3 py-3">
                <p className="text-sm font-medium">{user.name}</p>
                <p className="text-xs text-muted-foreground">{user.email}</p>
                <Badge variant={user.role === "admin" ? "default" : "secondary"} className="mt-1.5">
                    {user.role}
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
            <td className="min-w-64 px-3 py-3">
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
                    <Message error={error} success={success} />
                </div>
            </td>
        </tr>
    )
}

const UsersSection = ({
    users,
    clients,
    currentUserId,
    onCreated,
    onChanged,
}: {
    users: AdminUser[]
    clients: Client[]
    currentUserId: string
    onCreated: () => Promise<void>
    onChanged: (user: AdminUser) => void
}) => {
    const [name, setName] = useState("")
    const [email, setEmail] = useState("")
    const [password, setPassword] = useState("")
    const [assigned, setAssigned] = useState<string[]>([])
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

        setSaving(true)
        try {
            await createAdminUser({
                name: name.trim(),
                email: email.trim(),
                password,
                client_ids: assigned,
            })
            setSuccess(`User ${email.trim()} created`)
            setName("")
            setEmail("")
            setPassword("")
            setAssigned([])
            await onCreated()
        } catch (err) {
            setError(getApiErrorMessage(err))
        } finally {
            setSaving(false)
        }
    }

    return (
        <Section
            title="Users"
            description="Create accounts and manage client access."
        >
            <form onSubmit={handleSubmit} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                <Field label="Name *">
                    <Input value={name} onChange={(e) => setName(e.target.value)} disabled={saving} />
                </Field>
                <Field label="Email *">
                    <Input
                        type="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        autoComplete="off"
                        disabled={saving}
                    />
                </Field>
                <Field label="Password *">
                    <Input
                        type="password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        autoComplete="new-password"
                        disabled={saving}
                    />
                </Field>
                <div className="flex flex-col gap-1.5 text-sm lg:col-span-2">
                    <span className="text-muted-foreground">Assigned clients</span>
                    <ClientPicker
                        clients={clients}
                        selected={assigned}
                        onChange={setAssigned}
                        disabled={saving}
                    />
                </div>
                <div className="flex flex-col justify-end gap-3">
                    <Message error={error} success={success} />
                    <Button type="submit" disabled={saving} className="w-fit">
                        {saving ? "Creating…" : "Create user"}
                    </Button>
                </div>
            </form>

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
                                    onChanged={onChanged}
                                />
                            ))
                        )}
                    </tbody>
                </table>
            </div>
        </Section>
    )
}

/* ------------------------------------------------------------------ */
/* Documents                                                           */
/* ------------------------------------------------------------------ */

const DocumentsSection = ({
    documents,
    users,
    onChanged,
}: {
    documents: DocumentResponse[]
    users: AdminUser[]
    onChanged: () => Promise<void>
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

        // Upload with limited concurrency: sequential awaits made multi-file
        // uploads needlessly slow, while unbounded Promise.all can overwhelm
        // the browser/server with large PDFs.
        const fileCount = files.length

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
        if (fileRef.current) fileRef.current.value = ""

        const ok = fileCount - errors.length
        if (ok > 0) setSuccess(`Uploaded ${ok} ${ok === 1 ? "document" : "documents"}`)
        if (errors.length > 0) setError(errors.join(" "))

        setFiles([])
        await onChanged()
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
            await onChanged()
        } catch (err) {
            setError(getApiErrorMessage(err))
        }
    }

    return (
        <Section
            title="Documents"
            description="Upload knowledge-base files and assign them to users."
        >
            <form onSubmit={handleSubmit} className="grid gap-4 lg:grid-cols-2">
                <Field label="Assign to users *">
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
                    <Field label="Files (PDF, TXT, Markdown) *">
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
                                                className="rounded p-1.5 text-muted-foreground"
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

const QueryHistorySection = ({
    history,
    loading,
    onRefresh,
    onDelete,
}: {
    history: AdminHistoryItem[]
    loading: boolean
    onRefresh: () => Promise<void>
    onDelete: (id: string) => Promise<void>
}) => {
    const { confirm } = useDialogs()
    const [showSql, setShowSql] = useState<string | null>(null)

    if (loading) {
        return (
            <div className="flex items-center gap-2 py-16 text-sm text-muted-foreground">
                <Loader2 className="size-4" />
                Loading query history...
            </div>
        )
    }

    return (
        <Section
            title="Query History"
            description="All analysis queries executed by users. SQL is visible only to admins."
        >
            <div className="flex items-center justify-between">
                <Button variant="outline" size="sm" onClick={onRefresh} disabled={loading}>
                    <Loader2 className="size-4 mr-2 animate-spin" />
                    Refresh
                </Button>
                <span className="text-sm text-muted-foreground">
                    {history.length} query{history.length !== 1 ? "s" : ""}
                </span>
            </div>

            {history.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-8">No queries yet.</p>
            ) : (
                <div className="overflow-x-auto rounded-md border">
                    <table className="w-full">
                        <thead className="bg-muted/50">
                            <tr>
                                <th className={tableHeadClass}>Title / Question</th>
                                <th className={tableHeadClass}>Database</th>
                                <th className={tableHeadClass}>Rows</th>
                                <th className={tableHeadClass}>Created</th>
                                <th className={tableHeadClass}>SQL</th>
                                <th className={tableHeadClass} />
                            </tr>
                        </thead>
                        <tbody>
                            {history.map((item) => (
                                <tr key={item.id} className="border-t">
                                    <td className="max-w-xs truncate px-3 py-2.5 text-sm" title={item.question}>
                                        <p className="font-medium truncate">{item.title || item.question}</p>
                                        <p className="text-xs text-muted-foreground truncate">{item.question}</p>
                                    </td>
                                    <td className={tableCellClass}>{item.database}</td>
                                    <td className={tableCellClass}>{item.row_count ?? "—"}</td>
                                    <td className={tableCellClass}>
                                        {new Date(item.created_at).toLocaleString()}
                                    </td>
                                    <td className={tableCellClass}>
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            onClick={() => setShowSql(item.id === showSql ? null : item.id)}
                                            className="text-xs"
                                        >
                                            {showSql === item.id ? "Hide SQL" : "Show SQL"}
                                        </Button>
                                    </td>
                                    <td className="px-3 py-2.5 text-right">
                                        <Button
                                            variant="ghost"
                                            size="icon"
                                            className="text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                                            onClick={async () => {
                                                const approved = await confirm({
                                                    title: "Delete query history?",
                                                    description: "This query record will be removed.",
                                                    confirmLabel: "Delete",
                                                    destructive: true,
                                                })
                                                if (approved) {
                                                    await onDelete(item.id)
                                                }
                                            }}
                                            aria-label="Delete"
                                        >
                                            <Trash2 className="size-3.5" />
                                        </Button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            {showSql && (
                <div className="mt-4 rounded-xl border border-border/50 bg-muted/50 p-4">
                    <div className="flex items-center justify-between mb-2">
                        <h3 className="text-sm font-medium text-foreground">SQL Query</h3>
                        <Button variant="ghost" size="sm" onClick={() => setShowSql(null)}>
                            <X className="size-3.5" />
                        </Button>
                    </div>
                    <pre className="p-3 rounded bg-muted text-xs font-mono overflow-x-auto max-h-96 overflow-y-auto">
                        {history.find(h => h.id === showSql)?.sql || ""}
                    </pre>
                </div>
            )}
        </Section>
    )
}

/* ------------------------------------------------------------------ */

const AdminPanel = ({ currentUserId }: { currentUserId: string }) => {
    const { refreshDocuments: refreshSidebarDocuments } = useWorkspace()

    const [clients, setClients] = useState<Client[]>([])
    const [users, setUsers] = useState<AdminUser[]>([])
    const [documents, setDocuments] = useState<DocumentResponse[]>([])
    const [queryHistory, setQueryHistory] = useState<AdminHistoryItem[]>([])
    const [loading, setLoading] = useState(true)
    const [loadError, setLoadError] = useState<string | null>(null)
    const [queryHistoryLoading, setQueryHistoryLoading] = useState(false)

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

    const loadQueryHistory = useCallback(async () => {
        setQueryHistoryLoading(true)
        try {
                const history = await adminListHistory()
            setQueryHistory(history)
        } catch (err) {
            console.error("Failed to load query history:", err)
        } finally {
            setQueryHistoryLoading(false)
        }
    }, [])

        const handleDeleteHistory = async (id: string) => {
            await deleteHistory(id)
            await loadQueryHistory()
        }

        const handleUserChanged = (updated: AdminUser) =>
            setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)))

        useEffect(() => {
        Promise.all([listAdminClients(), listAdminUsers(), getAllDocuments()])
            .then(([clientList, userList, documentList]) => {
                setClients(clientList)
                setUsers(userList)
                setDocuments(documentList)
            })
            .catch((err) => setLoadError(getApiErrorMessage(err)))
            .finally(() => setLoading(false))
    }, [])

    useEffect(() => {
            let active = true
                const load = async () => {
                    await loadQueryHistory()
                    if (!active) return
                }
                load()
                return () => {
                    active = false
                }
            }, [loadQueryHistory])

    return (
        <TooltipProvider>
            <div className="min-h-0 flex-1 overflow-y-auto bg-transparent">
                <div className="mx-auto w-full max-w-6xl p-6 md:p-8">
                    <div className="mb-6">
                        <h1 className="text-xl font-semibold tracking-tight">Administration</h1>
                        <p className="mt-1 text-sm text-muted-foreground">
                            Manage clients, users and document access.
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

                            <Tabs defaultValue="clients" className="flex flex-col gap-4">
                                <TabsList className="w-fit">
                                    <TabsTrigger value="clients">Clients</TabsTrigger>
                                    <TabsTrigger value="users">Users</TabsTrigger>
                                    <TabsTrigger value="documents">Documents</TabsTrigger>
                                                                    <TabsTrigger value="query-history">Query History</TabsTrigger>
                                                                </TabsList>

                                                                <TabsContent value="clients">
                                                                    <ClientsSection
                                                                        clients={clients}
                                                                        onCreated={loadClients}
                                                                    />
                                                                </TabsContent>

                                                                <TabsContent value="users">
                                                                    <UsersSection
                                                                        users={users}
                                                                        clients={clients}
                                                                        currentUserId={currentUserId}
                                                                        onCreated={loadUsers}
                                                                        onChanged={handleUserChanged}
                                                                    />
                                                                </TabsContent>

                                                                <TabsContent value="documents">
                                                                    <DocumentsSection
                                                                        documents={documents}
                                                                        users={users}
                                                                        onChanged={loadDocuments}
                                                                    />
                                                                </TabsContent>

                                                                <TabsContent value="query-history">
                                                                    <QueryHistorySection
                                                                        history={queryHistory}
                                                                        loading={queryHistoryLoading}
                                                                        onRefresh={loadQueryHistory}
                                                                                                                                        onDelete={handleDeleteHistory}
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