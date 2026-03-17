import { NextResponse } from 'next/server';

const CHATWOOT_BASE_URL = "http://44.215.200.55:3000";
const CHATWOOT_USER_TOKEN = "MDrsGNERoskafLdnYzVB8KR2";
const ACCOUNT_ID = "1"; 
const INBOX_ID = "4";

export async function POST() {
  try {
    // 1. Create a unique anonymous Contact in Chatwoot
    const contactRes = await fetch(`${CHATWOOT_BASE_URL}/api/v1/accounts/${ACCOUNT_ID}/contacts`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'api_access_token': CHATWOOT_USER_TOKEN
      },
      body: JSON.stringify({
        // Generates a random name like "CRWD Visitor - 4921"
        name: `CRWD Visitor - ${Math.floor(Math.random() * 10000)}`, 
      })
    });
    
    const contactData = await contactRes.json();
    const contactId = contactData.payload.contact.id;

    // 2. Create a new Conversation attached to that Contact and Inbox
    const convRes = await fetch(`${CHATWOOT_BASE_URL}/api/v1/accounts/${ACCOUNT_ID}/conversations`, {
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
    });

    const convData = await convRes.json();
    
    // Return the newly generated conversation ID to the frontend!
    return NextResponse.json({ conversationId: convData.id });
    
  } catch (error) {
    console.error("Failed to initialize Chatwoot session:", error);
    return NextResponse.json({ error: "Failed to initialize chat" }, { status: 500 });
  }
}