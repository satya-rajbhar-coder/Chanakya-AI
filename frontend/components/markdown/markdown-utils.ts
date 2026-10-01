// export const copyToClipboard = async (
//     text: string
// ): Promise<boolean> => {
//     try {
//         await navigator.clipboard.writeText(text)
//         return true
//     } catch {
//         return false
//     }
// }


export const copyToClipboard = async (
    text: string
): Promise<boolean> => {
    if (!text) {
        return false
    }

    try {
        if (
            typeof navigator !== "undefined" &&
            navigator.clipboard &&
            window.isSecureContext
        ) {
            await navigator.clipboard.writeText(text)
            return true
        }
    } catch (error) {
        console.warn("Clipboard API failed:", error)
    }

    try {
        const textarea = document.createElement("textarea")

        textarea.value = text
        textarea.setAttribute("readonly", "")
        textarea.style.position = "fixed"
        textarea.style.opacity = "0"
        textarea.style.pointerEvents = "none"

        document.body.appendChild(textarea)

        textarea.focus()
        textarea.select()
        textarea.setSelectionRange(0, textarea.value.length)

        const success = document.execCommand("copy")

        document.body.removeChild(textarea)

        return success
    } catch (error) {
        console.error("Copy failed:", error)
        return false
    }
}
