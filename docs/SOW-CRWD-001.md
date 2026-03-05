# STATEMENT OF WORK

**SOW ID:** SOW-CRWD-001  
**Project:** CRWD AI  
**Date:** January 22, 2026  
**Between:** Discover IT Labs ("Provider") AND CRWD ("Client")

---

## 1. Executive Summary

CRWD is transitioning from manual, high-touch operations to a scalable Consumer Intelligence Platform. Currently, critical workflows rely on manual audits and a legacy communication system.

This Statement of Work outlines the engagement of a dedicated AI Engineering Pod to build the "CRWD Intelligence Hive." This engagement includes both the "Headless" backend intelligence (Verification, Fraud) and the Full-Stack implementation of the AI Chatbot interface, ensuring a seamless user experience for CRWD admins.

---

## 2. Engagement Model: Monthly Retainer

The Provider will work on a Fixed-Capacity Monthly Retainer, functioning as a flexible extension of the Client's engineering team.

- **Estimated Start Date:** Feb 1, 2026
- **Estimated Duration:** 3 - 4 Months
- **Team Capacity:** 3 engineering resources
- **Sprint Cadence:** 2-Week Sprints with weekly demos.

### 2.1 The Engineering Pod (Multidisciplinary)

The Client is allocated a dedicated team for the duration of the retainer. The composition may flex between Backend/Data and Frontend based on the active sprint focus.

- **1x AI Solutions Architect & Backend Engineer (Lead):** System design, API specs, and technical liaison.
- **1x Senior Full-Stack AI Engineer (Full-Time):** A hybrid engineer capable of building the complex Python agent logic and the React-based Chatbot UI interfaces.
- **1x Data Engineer/QA:** Responsible for ETL pipelines, database structuring, and "Red Teaming" fraud models.

---

## 3. Scope of Work & Roadmap

### Foundation & Data Backbone

**Objective:** Transform unstructured S3/CSV data into a queryable "Intelligence Database."

- **Infrastructure:** Provisioning AWS Aurora (Postgres) and Qdrant (Vector DB).
- **Data Pipeline:** Ingesting historic Member Profiles and Transactions from S3 buckets/CSVs.
- **Identity Graph:** Creating "Shadow Profiles" to link users via Device IDs and IP addresses.
- **Deliverable:** Secure API environment and normalized Intelligence Database.

### Project 1 - The "Auditor" Agent (Verification)

**Objective:** Automate manual receipt reviews.

- **Vision Pipeline:** GPT-4o Vision to extract Merchant, Date, and Line Items.
- **Validation Engine:** Logic to check Price, Quantity, and SKU, names, address, deliverables against Campaign Rules.
- **Vendor Rules:** Custom parsing for Target, Amazon, Sprouts, etc.

### Project 2 - The "Sentinel" Agent (Fraud)

**Objective:** Prevent financial loss before payout.

- **Duplicate Detection:** Perceptual hashing to block re-submitted or stolen receipt images.
- **Risk Scoring:** Weighted algorithm analyzing Reliability (History), Velocity, along with their fraud score.
- **Actions:** Block to create new profiles similar/matching suspected profiles.

### Project 3 - The "Concierge" (Chatbot & UI)

**Objective:** Deploy a Full-Stack AI Assistant to reduce the 4,000+ message load.

#### Backend (The Brain)

- **Knowledge Base:** RAG system indexing FAQs, Campaign Briefs, and past conversations.
- **Intent Router:** Distinguishing between "Tier 1" (Auto-Reply) and "Tier 2" (Human Review).

#### Frontend (The Interface)

- **Admin Copilot Widget:** A React-based "Sidecar" component for the CMS. It observes the active conversation and suggests "Draft Responses" in real-time for the Admin to approve/edit.
- **Chat UI Component:** A clean, reusable chat interface (React) supporting streaming responses, which the Client's engineer (Jay) can embed into the Mobile App if desired.

---

## 4. Technical Architecture

- **Backend:** Python (FastAPI / LangGraph) on AWS Lambda/Fargate.
- **Frontend (Chatbot only):** React / TypeScript.
- **Integration:**
  - **Data:** exposed via APIs.
  - **UI:** The Provider delivers the Chatbot UI as a NPM Package or an Embeddable Component that could integrate into the main application shell.

---

## 5. Roles & Responsibilities

### Provider (Discover IT Labs)

- End-to-End development of AI Agents (Logic + Data).
- Development of the Chatbot UI components (React).
- Infrastructure management (AWS/OpenAI).

### Client (CRWD)

- **Integration:** Integrating the provided Chatbot UI component into the main Mobile App/CMS navigation structure working with Discover IT Labs engineers.
- **Data Access:** Providing S3 access and fraud heuristics documentation.
- **UI Integration:** CRWD's internal engineering remains the owner of the core Mobile App and CMS codebase; Provider delivers "plug-in" capabilities.

---

## 6. Acceptance

**Agreed and Accepted:**

**For CRWD:**  
Name: Ryan Chen  
Title: CEO  
Date: Jan 27, 2026

**For Discover IT Labs:**  
Name: Ritesh Johar  
Title: CEO  
Date: Jan 27, 2026

---
