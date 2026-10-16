import DocumentsChat from "@/components/chat/DocumentsChat";

export default async function ConversationPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  return <DocumentsChat key={id} conversationId={id} />;
}
