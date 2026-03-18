import { NextResponse } from 'next/server';

const CHATWOOT_BASE_URL = "http://44.215.200.55:3000";
const CHATWOOT_USER_TOKEN = "MDrsGNERoskafLdnYzVB8KR2";
const ACCOUNT_ID = "1";
const INBOX_ID = "4";
const INBOX_IDENTIFIER = "7dwZ4tNiiDcrEKWReWiEEoK2";

export async function POST() {
  try {
    // 1. Create contact via PUBLIC API — only way to get pubsub_token
    const contactRes = await fetch(
      `${CHATWOOT_BASE_URL}/public/api/v1/inboxes/${INBOX_IDENTIFIER}/contacts`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          identifier: `visitor_${Math.floor(Math.random() * 1000000)}`,
          name: `CRWD Visitor - ${Math.floor(Math.random() * 10000)}`,
        })
      }
    );
    const contactData = await contactRes.json();
    console.log("Contact created:", contactData);

    const contactId   = contactData.id;
    const pubsubToken = contactData.pubsub_token;

    // 2. Create conversation via ADMIN API
    const convRes = await fetch(
      `${CHATWOOT_BASE_URL}/api/v1/accounts/${ACCOUNT_ID}/conversations`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'api_access_token': CHATWOOT_USER_TOKEN
        },
        body: JSON.stringify({
          inbox_id: INBOX_ID,
          contact_id: contactId,
          status: "open"
        })
      }
    );
    const convData = await convRes.json();
    console.log("Conversation created:", convData.id);

    return NextResponse.json({
      conversationId: convData.id,
      pubsubToken,
    });

  } catch (error) {
    console.error("❌ Init Chat Error:", error);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}