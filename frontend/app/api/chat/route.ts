import { createOpenAI } from "@ai-sdk/openai";
import { embed, streamText } from "ai";
import { z } from "zod";

import {
  assertSessionTenant,
  buildRetrievalQuery,
  fetchRecentMessages,
  formatChunksAsContext,
  insertMessage,
  retrieveHybrid,
} from "@/lib/rag";
import { getTenantId } from "@/lib/db";

const messagePartSchema = z.object({
  type: z.string(),
  text: z.string().optional(),
});

const chatMessageSchema = z.object({
  role: z.enum(["user", "assistant", "system"]),
  content: z.string().optional(),
  parts: z.array(messagePartSchema).optional(),
});

const bodySchema = z.object({
  id: z.string().optional(),
  sessionId: z.string().uuid(),
  messages: z.array(chatMessageSchema).min(1),
});

function messageText(message: z.infer<typeof chatMessageSchema>): string {
  if (message.content?.trim()) return message.content.trim();
  const part = message.parts?.find((p) => p.type === "text" && p.text?.trim());
  return part?.text?.trim() ?? "";
}

function latestUserMessage(messages: z.infer<typeof chatMessageSchema>[]): string {
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    if (messages[i].role !== "user") continue;
    const text = messageText(messages[i]);
    if (text) return text;
  }
  return "";
}

function toModelMessages(messages: z.infer<typeof chatMessageSchema>[]) {
  return messages
    .filter((m) => m.role === "user" || m.role === "assistant")
    .map((m) => ({
      role: m.role as "user" | "assistant",
      content: messageText(m),
    }))
    .filter((m) => m.content.length > 0);
}

const openai = createOpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

export async function POST(req: Request) {
  const parsed = bodySchema.safeParse(await req.json());
  if (!parsed.success) {
    return Response.json({ error: parsed.error.flatten() }, { status: 400 });
  }

  const { sessionId, messages } = parsed.data;
  const message = latestUserMessage(messages);
  if (!message) {
    return Response.json({ error: "No user message in payload" }, { status: 400 });
  }

  const tenantId = getTenantId();

  try {
    await assertSessionTenant(sessionId, tenantId);
  } catch (error) {
    const detail = error instanceof Error ? error.message : "Invalid session";
    return Response.json({ error: detail }, { status: 403 });
  }

  const recent = await fetchRecentMessages(sessionId, 6);
  const retrievalText = buildRetrievalQuery(message, recent);

  const { embedding } = await embed({
    model: openai.embedding("text-embedding-3-small"),
    value: retrievalText,
  });

  const chunks = await retrieveHybrid({
    tenantId,
    keywordQuery: message,
    embedding,
    limit: 8,
  });

  await insertMessage({ sessionId, role: "user", content: message });

  const result = streamText({
    model: openai("gpt-4o-mini"),
    system: formatChunksAsContext(chunks),
    messages: toModelMessages(messages),
    onFinish: async ({ text }) => {
      await insertMessage({
        sessionId,
        role: "assistant",
        content: text,
        metadata: { chunk_ids: chunks.map((chunk) => chunk.id) },
      });
    },
  });

  return result.toDataStreamResponse();
}
