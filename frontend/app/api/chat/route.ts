import { NextResponse } from 'next/server';

const CHATWOOT_BASE_URL = "http://44.215.200.55:3000";
const CHATWOOT_USER_TOKEN = "MDrsGNERoskafLdnYzVB8KR2"; 
const ACCOUNT_ID = "1"; 

export async function POST(req: Request) {
  try {
    const { message, conversationId } = await req.json();
    
    console.log(`\n--- [DEBUG] SENDING MESSAGE ---`);
    console.log(`Target Conversation ID: ${conversationId}`);
    console.log(`Message: "${message}"`);

    if (!conversationId) {
      console.error("ERROR: Conversation ID is missing!");
      return NextResponse.json({ error: "Missing conversation ID" }, { status: 400 });
    }

    const chatwootUrl = `${CHATWOOT_BASE_URL}/api/v1/accounts/${ACCOUNT_ID}/conversations/${conversationId}/messages`;
    console.log(`Hitting Chatwoot URL: ${chatwootUrl}`);

    const response = await fetch(chatwootUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'api_access_token': CHATWOOT_USER_TOKEN
      },
      body: JSON.stringify({
        content: message,
        message_type: 0, 
        private: false
      })
    });

    const data = await response.json();

    if (!response.ok) {
      console.error("❌ CHATWOOT REJECTED THE MESSAGE!");
      console.error("Chatwoot Error Details:", data);
      return NextResponse.json({ error: "Chatwoot rejected", details: data }, { status: response.status });
    }

    console.log("✅ SUCCESS! Message saved to Chatwoot with ID:", data.id);
    return NextResponse.json(data);
    
  } catch (error) {
    console.error("❌ FATAL SERVER ERROR in /api/chat:", error);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}
export async function GET(req:any) {
  const { searchParams } = new URL(req.url);
  const conversationId = searchParams.get('conversationId');

  const response = await fetch(`${CHATWOOT_BASE_URL}/api/v1/accounts/${ACCOUNT_ID}/conversations/${conversationId}/messages`, {
    method: 'GET',
    headers: {
      'api_access_token': CHATWOOT_USER_TOKEN
    }
  });

  return NextResponse.json(await response.json());
}