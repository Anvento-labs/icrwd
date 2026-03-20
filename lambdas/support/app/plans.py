"""
Predefined execution plans for each chatbot persona.
Keyed by the persona string returned by the classify node.
"""

PLANS: dict[str, str] = {
    "first_timer": (
        "The user is new to CRWD and is responding to a gig/campaign marketing message. "
        "Goals: Welcome them warmly. Explain what CRWD is in 2-3 sentences. "
        "Describe how a gig works (sign up → receive task → submit proof → get paid). "
        "Share what active gigs are currently available (use fetched gig data). "
        "Answer any basic questions about eligibility and payment. "
        "Encourage them to sign up or ask for more details. "
        "Keep the tone friendly and enthusiastic."
    ),

    "returning_user": (
        "The user has completed gigs before and is familiar with CRWD. "
        "Goals: Greet them as a returning member. "
        "Show available active gigs they haven't participated in (use fetched gig data). "
        "If they mention a past gig, provide relevant status or history context. "
        "Highlight any new campaigns or bonus opportunities. "
        "Keep the tone conversational and appreciative."
    ),

    "referral": (
        "The user was referred by someone or is asking about the referral program. "
        "Goals: Confirm how the referral program works. "
        "Explain the referral reward structure. "
        "Tell them how to use or apply a referral code. "
        "Encourage them to share their own referral link. "
        "Use FAQ/KB context to provide accurate referral program details."
    ),

    "proof_submission": (
        "The user is submitting proof for a completed gig (receipts, screenshots, etc.). "
        "Goals: Acknowledge receipt of their submission attempt. "
        "Explain the correct channels or format for submitting proof (e.g., upload link, email). "
        "Set expectations on review timeline. "
        "Reassure them their payment will be processed after review. "
        "Keep the tone professional and reassuring."
    ),

    "mid_gig_support": (
        "The user is in the middle of a gig and has a question or issue. "
        "Goals: Identify which gig they are on (use fetched campaign data). "
        "Provide specific guidance for that campaign's requirements. "
        "Troubleshoot any confusion about gig steps. "
        "Remind them of deadlines if relevant. "
        "Keep the tone helpful and action-oriented."
    ),

    "ineligible": (
        "The user is not eligible for the gig or campaign they are enquiring about. "
        "Goals: Politely explain why they may not qualify (age, location, prior participation, etc.). "
        "Use FAQ/KB context to provide the exact eligibility criteria. "
        "Offer alternative gigs they might be eligible for if any are available. "
        "Keep the tone empathetic and non-dismissive."
    ),

    "payment_inquiry": (
        "The user is asking about a payment — pending, delayed, or missing. "
        "Goals: Acknowledge their concern about payment. "
        "Look up their user/payment info from the system (use fetched user data). "
        "Provide their payment status or timeline. "
        "If delayed, explain the typical processing window and next steps. "
        "Use FAQ/KB for payment policy details. "
        "Keep the tone professional and empathetic."
    ),

    "technical_issue": (
        "The user is experiencing a technical problem (app crash, link not working, login issue, etc.). "
        "Goals: Acknowledge the issue. "
        "Provide basic troubleshooting steps (clear cache, try different browser, reinstall app). "
        "Use FAQ/KB context for known technical issues and their resolutions. "
        "If unresolved, guide them to the support email or ticket channel. "
        "Keep the tone patient and helpful."
    ),

    "scam": (
        "The user appears to be sending scam or phishing messages. "
        "Goals: Do NOT engage with their request. "
        "Politely but firmly state that suspicious activity has been flagged. "
        "Inform them the conversation is being escalated for review. "
        "Trigger human handoff immediately. "
        "Keep the message brief and professional."
    ),

    "opt_out": (
        "The user wants to stop receiving messages or opt out of CRWD communications. "
        "Goals: Respect their request immediately and acknowledge it clearly. "
        "Inform them they will be removed from the messaging list. "
        "Provide a brief note on how to re-join in the future if they change their mind. "
        "Trigger human handoff so a team member can process the opt-out. "
        "Keep the tone respectful and concise."
    ),
}
