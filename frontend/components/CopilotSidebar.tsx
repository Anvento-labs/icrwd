'use client';

import { useState, useEffect, useRef } from 'react';

interface Message {
  role: 'user' | 'ai';
  text: string;
}

export default function CopilotSidebar() {
  const [isOpen, setIsOpen] = useState<boolean>(false);
  const [inputText, setInputText] = useState<string>("");
  const [isThinking, setIsThinking] = useState<boolean>(false);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const [messages, setMessages] = useState<Message[]>([
    { role: 'ai', text: 'Hello! I am your CRWD AI Copilot. How can I help you optimize your campaigns today?' }
  ]);

  // Auto-scroll to bottom whenever messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isThinking]);

  // Fetch a fresh conversation ID (Your existing logic)
  useEffect(() => {
    if (isOpen && !activeConversationId) {
      const initializeChat = async () => {
        try {
          const res = await fetch('/api/init-chat', { method: 'POST' });
          const data = await res.json();
          if (data.conversationId) setActiveConversationId(data.conversationId);
        } catch (error) {
          console.error("Could not initialize chat session", error);
        }
      };
      initializeChat();
    }
  }, [isOpen, activeConversationId]);

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) console.log("File selected:", file.name);
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault(); 
    if (!inputText.trim()) return;

    const userMessage = inputText;
    setInputText(""); 

    setMessages(prev => [...prev, { role: 'user', text: userMessage }]);
    setIsThinking(true);

    try {
      if (activeConversationId) {
        await fetch('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: userMessage, conversationId: activeConversationId }),
        });
        setTimeout(fetchLatestMessages, 4000);
      } else {
        // Fallback for UI testing if backend is paused
        setTimeout(() => {
          setMessages(prev => [...prev, { role: 'ai', text: "This is a beautiful placeholder response for your demo tomorrow!" }]);
          setIsThinking(false);
        }, 2500);
      }
    } catch (error) {
      setIsThinking(false);
    }
  };

  const fetchLatestMessages = async () => {
    if (!activeConversationId) return;
    try {
      const res = await fetch(`/api/chat?conversationId=${activeConversationId}`);
      const data = await res.json();
      if (data && data.payload) {
        const chatwootMessages = data.payload.map((msg: any) => ({
          role: msg.message_type === 0 ? 'user' : 'ai',
          text: msg.content
        })).reverse(); 

        setMessages([
          { role: 'ai', text: 'Hello! I am your CRWD AI Copilot. How can I help you optimize your campaigns today?' }, 
          ...chatwootMessages
        ]);
      }
      setIsThinking(false);
    } catch (error) {
      setIsThinking(false);
    }
  };

  return (
    <>
      {/* Floating Toggle Button (Pulsing effect for attention) */}
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          className="fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-gradient-to-tr from-yellow-500 to-yellow-300 text-black shadow-[0_0_20px_rgba(250,204,21,0.3)] transition-all duration-300 hover:scale-110 hover:shadow-[0_0_30px_rgba(250,204,21,0.5)]"
        >
          <svg className="h-7 w-7" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
          </svg>
        </button>
      )}

      {/* Glassmorphism Background Overlay */}
      {isOpen && (
        <div 
          className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm transition-opacity duration-300"
          onClick={() => setIsOpen(false)}
        />
      )}

      {/* The Copilot Sidebar Panel */}
      <div
        className={`fixed right-0 top-0 z-50 flex h-screen w-full max-w-[400px] flex-col border-l border-white/10 bg-[#09090b] shadow-2xl transition-transform duration-500 cubic-bezier(0.16, 1, 0.3, 1) ${
          isOpen ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        {/* Header - Glassmorphic */}
        <div className="flex items-center justify-between border-b border-white/10 bg-white/5 px-6 py-4 backdrop-blur-md">
          <div className="flex items-center gap-4">
            <div className="relative">
              <img 
                src="/joincrwd_logo.jpeg" 
                alt="CRWD Logo" 
                className="h-10 w-10 rounded-xl object-cover shadow-sm" 
              />
              <span className="absolute -bottom-1 -right-1 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-[#09090b]">
                <span className="h-2 w-2 rounded-full bg-green-500 animate-pulse"></span>
              </span>
            </div>
            <div>
              <h2 className="text-base font-bold text-white tracking-wide">CRWD Copilot</h2>
              <p className="text-xs text-gray-400">Powered by Anvento Labs</p>
            </div>
          </div>
          <button 
            onClick={() => setIsOpen(false)}
            className="rounded-full p-2 text-gray-400 hover:bg-white/10 hover:text-white transition-all"
          >
            <svg className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Dynamic Chat History Area (Hide scrollbar for clean look) */}
        <div className="flex-1 overflow-y-auto p-5 space-y-6 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
          {messages.map((msg, index) => (
            <div key={index} className={`flex w-full gap-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              
              {/* AI Avatar */}
              {msg.role === 'ai' && (
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white/10 border border-white/20">
                  <svg className="h-4 w-4 text-yellow-400" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2a2 2 0 0 1 2 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 0 1 7 7h1a1 1 0 0 1 1 1v3a1 1 0 0 1-1 1h-1v1a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-1H2a1 1 0 0 1-1-1v-3a1 1 0 0 1 1-1h1a7 7 0 0 1 7-7h1V5.73A2 2 0 1 1 12 2z"/></svg>
                </div>
              )}

              <div className={`max-w-[80%] rounded-2xl p-4 text-[15px] leading-relaxed shadow-sm ${
                msg.role === 'user' 
                  ? 'rounded-tr-sm bg-gradient-to-br from-yellow-400 to-yellow-500 font-medium text-black shadow-yellow-500/20' 
                  : 'rounded-tl-sm border border-white/10 bg-[#18181b] text-gray-100'
              }`}>
                {msg.text}
              </div>

            </div>
          ))}

          {/* Animated 3-Dot Thinking State */}
          {isThinking && (
            <div className="flex w-full gap-3 justify-start">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white/10 border border-white/20">
                 <svg className="h-4 w-4 text-yellow-400" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2a2 2 0 0 1 2 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 0 1 7 7h1a1 1 0 0 1 1 1v3a1 1 0 0 1-1 1h-1v1a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-1H2a1 1 0 0 1-1-1v-3a1 1 0 0 1 1-1h1a7 7 0 0 1 7-7h1V5.73A2 2 0 1 1 12 2z"/></svg>
              </div>
              <div className="flex max-w-[80%] items-center gap-1.5 rounded-2xl rounded-tl-sm border border-white/10 bg-[#18181b] px-4 py-5 shadow-sm">
                <div className="h-2 w-2 animate-bounce rounded-full bg-gray-400 [animation-delay:-0.3s]"></div>
                <div className="h-2 w-2 animate-bounce rounded-full bg-gray-400 [animation-delay:-0.15s]"></div>
                <div className="h-2 w-2 animate-bounce rounded-full bg-gray-400"></div>
              </div>
            </div>
          )}
          
          {/* Invisible div to scroll to */}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <form onSubmit={handleSendMessage} className="border-t border-white/10 bg-[#09090b] p-4 pt-3">
          <div className="flex items-center rounded-2xl border border-white/10 bg-[#18181b] p-1.5 focus-within:border-yellow-500/50 focus-within:ring-1 focus-within:ring-yellow-500/50 transition-all duration-300 shadow-inner">
            
            {/* Attachment Button */}
            <label className="cursor-pointer rounded-xl p-2.5 text-gray-400 hover:bg-white/5 hover:text-white transition-colors">
              <input type="file" className="hidden" onChange={handleFileUpload} />
              <svg className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
              </svg>
            </label>

            <input
              type="text"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              placeholder="Message Copilot..."
              className="w-full bg-transparent px-3 text-[15px] text-white placeholder-gray-500 outline-none"
            />
            
            {/* Submit Button */}
            <button 
              type="submit" 
              disabled={!inputText.trim()}
              className="mr-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-yellow-400 text-black transition-all hover:bg-yellow-300 hover:shadow-[0_0_15px_rgba(250,204,21,0.4)] disabled:opacity-50 disabled:hover:shadow-none disabled:hover:scale-100"
            >
              <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 19.5l15-15m0 0H8.25m11.25 0v11.25" />
              </svg>
            </button>
          </div>
          <div className="mt-2 text-center">
            <span className="text-[10px] text-gray-500">Copilot can make mistakes. Consider verifying important information.</span>
          </div>
        </form>

      </div>
    </>
  );
}