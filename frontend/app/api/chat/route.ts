import { NextResponse } from 'next/server';

const CHATWOOT_BASE_URL = "http://44.215.200.55:3000";
const CHATWOOT_USER_TOKEN = "MDrsGNERoskafLdnYzVB8KR2";
const ACCOUNT_ID = "1";

export async function POST(req: Request) {
  try {
    const { message, conversationId } = await req.json();

    if (!conversationId) {
      return NextResponse.json({ error: "Missing conversation ID" }, { status: 400 });
    }

    const url = `${CHATWOOT_BASE_URL}/api/v1/accounts/${ACCOUNT_ID}/conversations/${conversationId}/messages`;

    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'api_access_token': CHATWOOT_USER_TOKEN
      },
      body: JSON.stringify({
        content: message,
        message_type: 0,  // incoming (from user)
        private: false
      })
    });

    const data = await response.json();

    if (!response.ok) {
      console.error("❌ Chatwoot rejected message:", data);
      return NextResponse.json({ error: "Chatwoot rejected", details: data }, { status: response.status });
    }

    console.log("✅ Message sent to Chatwoot, ID:", data.id);
    return NextResponse.json(data);

  } catch (error) {
    console.error("❌ Fatal error in /api/chat:", error);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}