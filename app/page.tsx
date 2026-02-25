"use client";

import { useState, useEffect } from "react";
import { generateClient } from "aws-amplify/data";
import type { Schema } from "@/amplify/data/resource";
import { Amplify } from "aws-amplify";
import outputs from "@/amplify_outputs.json";
import "@aws-amplify/ui-react/styles.css";
import { Authenticator } from "@aws-amplify/ui-react";
import styles from "./page.module.css";

Amplify.configure(outputs);

const client = generateClient<Schema>();

export default function App() {
  const [todos, setTodos] = useState<Array<Schema["Todo"]["type"]>>([]);
  const [inputValue, setInputValue] = useState("");

  function listTodos() {
    client.models.Todo.observeQuery().subscribe({
      next: (data) => setTodos([...data.items]),
    });
  }

  useEffect(() => {
    listTodos();
  }, []);

  function createTodo() {
    if (!inputValue.trim()) return;
    client.models.Todo.create({ content: inputValue });
    setInputValue("");
  }

  function deleteTodo(id: string) {
    client.models.Todo.delete({ id });
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter") createTodo();
  }

  return (
    <Authenticator>
      {({ signOut, user }) => (
        <div className={styles.page}>
          {/* Ambient glow dots */}
          <div className={styles.dot} style={{ top: "18%", left: "8%" }} />
          <div className={styles.dot} style={{ top: "55%", right: "6%" }} />
          <div className={styles.dotLarge} style={{ bottom: "25%", left: "15%" }} />
          <div className={styles.dot} style={{ top: "75%", right: "22%" }} />

          <nav className={styles.nav}>
            <div className={styles.logo}>
              <svg width="34" height="34" viewBox="0 0 34 34" fill="none">
                <rect x="3" y="3" width="10" height="10" rx="2" stroke="white" strokeWidth="1.8" />
                <rect x="21" y="3" width="10" height="10" rx="2" stroke="white" strokeWidth="1.8" />
                <rect x="3" y="21" width="10" height="10" rx="2" stroke="white" strokeWidth="1.8" />
                <rect x="21" y="21" width="10" height="10" rx="2" stroke="white" strokeWidth="1.8" />
              </svg>
              <span>CRWD</span>
            </div>
            {/* <div className={styles.navLinks}>
              <a href="#" className={styles.navActive}>Home</a>
              <a href="#">For Brands</a>
              <a href="#">Join CRWD</a>
              <a href="#">Live Feed</a>
            </div> */}
            <button className={styles.bookBtn} onClick={signOut}>Sign Out</button>
          </nav>

          <main className={styles.main}>
            <div className={styles.hero}>
              <p className={styles.eyebrow}>WELCOME BACK // {user?.signInDetails?.loginId}</p>
              {/* <h1 className={styles.headline}>
                Stop Wasting Time.<br />
                <span className={styles.accent}>Deploy Your Tasks.</span>
              </h1>
              <p className={styles.sub}>
                The only productivity platform that activates your focus on demand.
              </p> */}
            </div>

            {/* <div className={styles.inputWrapper}>
              <input
                className={styles.input}
                type="text"
                placeholder="I need to deploy..."
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
              />
              <p className={styles.hint}>
                Press <kbd className={styles.kbd}>Enter</kbd> to deploy your task
              </p>
            </div> */}

            {/* <div className={styles.actions}>
              <button className={styles.primaryBtn} onClick={createTodo}>
                DEPLOY ACTIVATION ⚡
              </button>
              <button className={styles.secondaryBtn}>
                WATCH LIVE FEED
              </button>
            </div> */}

            {todos.length > 0 && (
              <div className={styles.todoSection}>
                <div className={styles.sectionHeader}>
                  <span className={styles.sectionTitle}>ACTIVE DEPLOYMENTS</span>
                  <span className={styles.badge}>{todos.length} Active</span>
                </div>
                <ul className={styles.list}>
                  {todos.map((todo) => (
                    <li key={todo.id} className={styles.item}>
                      <span className={styles.bullet}>⚡</span>
                      <span className={styles.itemText}>{todo.content}</span>
                      <button className={styles.deleteBtn} onClick={() => deleteTodo(todo.id)}>✕</button>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className={styles.liveCards}>
              {/* <div className={styles.liveCard}>
                <span className={styles.liveLabel}>Latest activation</span>
                <span className={styles.liveActivity}><strong className={styles.accentText}>Arrow G.</strong> in Scottsdale just deployed [focus sprint]</span>
              </div>
              <div className={styles.liveCard}>
                <span className={styles.liveLabel}>Active CRWD right now:</span>
                <span className={styles.liveCount}>14,198 Humans</span>
              </div> */}
            </div>
          </main>
        </div>
      )}
    </Authenticator>
  );
}