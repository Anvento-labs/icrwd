"use client";

import { useState, useEffect } from "react";
import { generateClient } from "aws-amplify/data";
import type { Schema } from "@/amplify/data/resource";
import { Amplify } from "aws-amplify";
import outputs from "@/amplify_outputs.json";
import "@aws-amplify/ui-react/styles.css";
import { Authenticator } from "@aws-amplify/ui-react";

Amplify.configure(outputs);

const client = generateClient<Schema>();

// Clean, scoped CSS exclusively for the login screen
const LoginStyles = () => (
  <style dangerouslySetInnerHTML={{
    __html: `
    /* Scope layout ONLY to the login screen */
    [data-amplify-authenticator]:has([data-amplify-router]) {
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      background-color: #0a0a08;
      background-image: radial-gradient(circle at 50% -20%, rgba(255, 200, 0, 0.08), transparent 60%);
      font-family: 'Courier New', Courier, monospace;
    }

    /* Minimalist Glass Card */
    [data-amplify-authenticator] [data-amplify-router] {
      background: rgba(20, 20, 15, 0.4) !important;
      backdrop-filter: blur(24px) saturate(150%) !important;
      -webkit-backdrop-filter: blur(24px) saturate(150%) !important;
      border: 1px solid rgba(255, 200, 0, 0.1) !important;
      border-top: 1px solid rgba(255, 200, 0, 0.2) !important;
      border-radius: 16px !important;
      box-shadow: 0 30px 60px -12px rgba(0, 0, 0, 0.8),
                  inset 0 1px 0 rgba(255, 255, 255, 0.05) !important;
      width: 100% !important;
      max-width: 420px !important;
      padding: 2rem !important;
    }

    /* Amplify UI Theme Variables Overrides */
    [data-amplify-authenticator] {
      --amplify-colors-font-primary: white;
      --amplify-colors-font-secondary: rgba(255, 255, 255, 0.4);
      --amplify-colors-font-interactive: #FFC800;
      --amplify-colors-background-primary: transparent;
      --amplify-colors-background-secondary: transparent;
      --amplify-colors-border-primary: rgba(255, 255, 255, 0.1);
      --amplify-colors-border-focus: #FFC800;
      --amplify-components-fieldcontrol-color: white;
      --amplify-components-button-primary-background-color: #FFC800;
      --amplify-components-button-primary-hover-background-color: #e6b400;
      --amplify-components-button-primary-color: #0a0a08;
    }

    /* Clean up the inputs */
    [data-amplify-authenticator] .amplify-input {
      background-color: rgba(0, 0, 0, 0.3) !important;
      border-radius: 8px !important;
      padding: 0.8rem 1rem !important;
      transition: all 0.3s ease;
    }
    
    [data-amplify-authenticator] .amplify-input:focus {
      background-color: rgba(255, 200, 0, 0.03) !important;
      box-shadow: 0 0 0 2px rgba(255, 200, 0, 0.2) !important;
    }

    /* Bold Primary Button */
    [data-amplify-authenticator] .amplify-button--primary {
      border-radius: 8px !important;
      font-weight: 700 !important;
      letter-spacing: 0.15em !important;
      text-transform: uppercase !important;
      margin-top: 1.5rem !important;
      padding: 1rem !important;
      transition: transform 0.2s, box-shadow 0.2s !important;
    }
    
    [data-amplify-authenticator] .amplify-button--primary:hover {
      transform: translateY(-2px);
      box-shadow: 0 8px 20px rgba(255, 200, 0, 0.2) !important;
    }

    /* Active/Inactive Tabs */
    [data-amplify-authenticator] .amplify-tabs-item {
      color: rgba(255, 255, 255, 0.3) !important;
      border-color: transparent !important;
      padding-bottom: 1rem !important;
      letter-spacing: 0.1em;
    }
    [data-amplify-authenticator] .amplify-tabs-item[data-state="active"] {
      color: #FFC800 !important;
      border-color: #FFC800 !important;
    }
  `}} />
);

// Clean Logo Header for Login Card
const components = {
  Header() {
    return (
      <div className="flex flex-col items-center justify-center pb-8 pt-4">
        <div className="relative mb-4">
          <div className="absolute inset-0 bg-[#FFC800] blur-xl opacity-20 rounded-full"></div>
          <svg width="44" height="44" viewBox="0 0 34 34" fill="none" className="relative z-10">
            <rect x="3" y="3" width="10" height="10" rx="2" stroke="#FFC800" strokeWidth="1.8" />
            <rect x="21" y="3" width="10" height="10" rx="2" stroke="#FFC800" strokeWidth="1.8" strokeOpacity="0.4" />
            <rect x="3" y="21" width="10" height="10" rx="2" stroke="#FFC800" strokeWidth="1.8" strokeOpacity="0.4" />
            <rect x="21" y="21" width="10" height="10" rx="2" stroke="#FFC800" strokeWidth="1.8" />
          </svg>
        </div>
        <h1 className="text-white text-2xl font-bold tracking-[0.4em] font-[Courier_New,Courier,monospace] ml-2">
          CRWD
        </h1>
      </div>
    );
  },
};

export default function App() {
  const [todos, setTodos] = useState<Array<Schema["Todo"]["type"]>>([]);

  function listTodos() {
    client.models.Todo.observeQuery().subscribe({
      next: (data) => setTodos([...data.items]),
    });
  }

  useEffect(() => {
    listTodos();
  }, []);

  function deleteTodo(id: string) {
    client.models.Todo.delete({ id });
  }

  return (
    <>
      <LoginStyles />
      <Authenticator components={components}>
        {({ signOut, user }) => (
          <div
            className="min-h-screen w-full bg-[#0a0a08] text-white font-[Courier_New,Courier,monospace] relative overflow-x-hidden flex flex-col selection:bg-[#FFC800]/30"
            style={{
              backgroundImage: `
                radial-gradient(ellipse 80% 50% at 50% -20%, rgba(255, 200, 0, 0.08) 0%, transparent 100%),
                radial-gradient(ellipse 60% 60% at 100% 100%, rgba(255, 200, 0, 0.04) 0%, transparent 100%)
              `
            }}
          >
            {/* Ambient Background Elements */}
            <div className="fixed inset-0 z-0 pointer-events-none" style={{ backgroundImage: 'linear-gradient(rgba(255,255,255,0.015) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.015) 1px, transparent 1px)', backgroundSize: '64px 64px' }}></div>
            <div className="fixed w-[4px] h-[4px] rounded-full bg-[#FFC800] shadow-[0_0_15px_5px_rgba(255,200,0,0.3)] pointer-events-none animate-[pulse_4s_ease-in-out_infinite]" style={{ top: "25%", left: "12%" }} />
            <div className="fixed w-[6px] h-[6px] rounded-full bg-[#FFC800]/80 shadow-[0_0_20px_6px_rgba(255,200,0,0.2)] pointer-events-none animate-[pulse_3s_ease-in-out_infinite_reverse]" style={{ bottom: "30%", right: "15%" }} />

            {/* Glassmorphic Top Nav */}
            <nav className="relative z-50 flex items-center justify-between py-5 px-6 sm:px-12 border-b border-white/[0.08] bg-[#0a0a08]/70 backdrop-blur-xl">
              <div className="flex items-center gap-3">
                <div className="relative flex items-center justify-center w-10 h-10 rounded-lg bg-white/[0.03] border border-white/[0.08]">
                  <svg width="22" height="22" viewBox="0 0 34 34" fill="none">
                    <rect x="3" y="3" width="10" height="10" rx="2" stroke="#FFC800" strokeWidth="2" />
                    <rect x="21" y="3" width="10" height="10" rx="2" stroke="#FFC800" strokeWidth="2" strokeOpacity="0.4" />
                    <rect x="3" y="21" width="10" height="10" rx="2" stroke="#FFC800" strokeWidth="2" strokeOpacity="0.4" />
                    <rect x="21" y="21" width="10" height="10" rx="2" stroke="#FFC800" strokeWidth="2" />
                  </svg>
                </div>
                <span className="text-[0.95rem] font-bold tracking-[0.25em] text-white/90 ml-1">CRWD</span>
              </div>

              <button
                className="group flex items-center gap-2 bg-transparent border border-white/10 text-white/70 py-2.5 px-6 rounded-lg text-[0.75rem] font-bold tracking-[0.1em] uppercase cursor-pointer transition-all duration-300 hover:bg-white/[0.05] hover:text-white hover:border-white/30"
                onClick={signOut}
              >
                Sign Out
                <span className="opacity-50 group-hover:opacity-100 transition-opacity">→</span>
              </button>
            </nav>

            <main className="relative z-10 flex-1 flex flex-col items-center pt-16 sm:pt-24 px-5 sm:px-6 pb-20 max-w-[840px] w-full mx-auto">

              {/* Cinematic Header Section */}
              <header className="w-full flex flex-col md:flex-row md:items-end justify-between gap-6 mb-12 border-b border-white/10 pb-8">
                <div>
                  <div className="flex items-center gap-3 mb-3">
                    <span className="flex h-2 w-2 relative">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#FFC800] opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-2 w-2 bg-[#FFC800]"></span>
                    </span>
                    <p className="text-[0.65rem] tracking-[0.3em] text-[#FFC800] uppercase font-bold">Secure Connection Established</p>
                  </div>
                  <h2 className="text-3xl md:text-4xl font-bold tracking-tight text-white mb-2">Deployment Center</h2>
                  <p className="text-sm tracking-[0.1em] text-white/40 uppercase">Operator // <span className="text-white/80">{user?.signInDetails?.loginId}</span></p>
                </div>

                <div className="flex flex-col gap-1 bg-white/[0.02] border border-white/5 rounded-lg p-4 min-w-[180px]">
                  <span className="text-[0.65rem] tracking-[0.2em] text-white/40 uppercase">System Status</span>
                  <div className="text-2xl font-bold text-white tracking-wider">
                    {todos.length} <span className="text-sm text-[#FFC800] tracking-[0.1em] font-normal">ACTIVE</span>
                  </div>
                </div>
              </header>

              {/* Glassmorphic List Section */}
              {todos.length > 0 ? (
                <div className="w-full">
                  <div className="flex items-center justify-between mb-4 px-2">
                    <span className="text-[0.7rem] tracking-[0.25em] text-white/30 uppercase font-bold">Live Feed</span>
                  </div>

                  <ul className="flex flex-col gap-3 p-0 m-0 list-none">
                    {todos.map((todo) => (
                      <li
                        key={todo.id}
                        className="group relative overflow-hidden flex items-center justify-between bg-white/[0.02] border border-white/[0.08] rounded-xl p-5 backdrop-blur-sm transition-all duration-300 hover:bg-white/[0.04] hover:border-[#FFC800]/30 hover:shadow-[0_8px_30px_rgba(255,200,0,0.05)]"
                      >
                        {/* Hover Gradient Effect */}
                        <div className="absolute top-0 left-0 w-1 h-full bg-[#FFC800] opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>

                        <div className="flex items-center gap-4">
                          <div className="flex items-center justify-center w-8 h-8 rounded-full bg-[#FFC800]/10 text-[#FFC800] text-[0.8rem]">
                            ⚡
                          </div>
                          <span className="text-[0.95rem] tracking-[0.02em] text-white/90">
                            {todo.content}
                          </span>
                        </div>

                        <button
                          className="flex items-center justify-center w-8 h-8 bg-transparent border border-transparent text-white/30 rounded-lg cursor-pointer transition-all duration-200 hover:text-[#ff5f56] hover:bg-[#ff5f56]/10 hover:border-[#ff5f56]/30"
                          onClick={() => deleteTodo(todo.id)}
                          title="Terminate Deployment"
                        >
                          ✕
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : (
                /* Beautiful Empty State */
                <div className="w-full flex flex-col items-center justify-center py-20 bg-white/[0.01] border border-white/[0.05] border-dashed rounded-2xl backdrop-blur-sm">
                  <div className="w-16 h-16 rounded-full bg-white/[0.03] flex items-center justify-center mb-4 border border-white/10">
                    <span className="text-2xl opacity-40">∅</span>
                  </div>
                  <p className="text-[0.85rem] tracking-[0.15em] text-white/40 uppercase">No active deployments</p>
                </div>
              )}
            </main>
          </div>
        )}
      </Authenticator>
    </>
  );
}