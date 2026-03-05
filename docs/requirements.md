# CRWD Intelligence System - Requirements Document

## Introduction

The CRWD Intelligence System is designed to automate critical workflows for CRWD's consumer intelligence platform. This document outlines functional requirements for three core business use cases that address current operational pain points and financial risks identified during stakeholder analysis.

### Target Users

- **CRWD Operations Team** (receipt verification and fraud review)
- **CRWD Customer Support Team** (message handling and user assistance)
- **CRWD Members** (receipt submission and support inquiries)

---

## Data Ingestion Requirements

### Historical Data Import

Requirements for system setup and data migration from existing sources.

### Requirement 0: Multi-Source Data Integration and Modeling

> **User Story:** As a data engineer/developer, I want to get data (user, campaign, and related entities) from defined sources and have a designed schema so that the system has a clear, consistent data model for ingestion, storage, and reporting.

**Requirements:**

- **GIVEN** the system requires user profile data
  - **WHEN** user data becomes available from CMS or S3 sources
  - **THEN** the system shall capture user profile information including identity verification status and contact details

- **GIVEN** the system requires campaign configuration data
  - **WHEN** campaign data becomes available from CSV files or configuration sources
  - **THEN** the system shall capture campaign rules including eligible products, merchants, date ranges, and payout criteria

- **GIVEN** the system requires transaction and audit data
  - **WHEN** transaction data becomes available from multiple sources
  - **THEN** the system shall capture submission records, receipt images, approval decisions, and audit trail information

- **GIVEN** the system needs to support fraud detection and verification workflows
  - **WHEN** designing data relationships
  - **THEN** the system shall maintain relationships between users, submissions, campaigns, and fraud indicators to enable pattern analysis

---

## Use Case 1: Receipt & Order Verification

### Requirement 1.1: Receipt Processing & Data Extraction

> **User Story:** As an operations team member, I want receipts to be automatically processed from any supported vendor so that I can review structured data instead of manually reading each receipt.

**Requirements:**

- **GIVEN** a receipt image has been submitted through mobile app or CMS
  - **WHEN** the system processes the receipt
  - **THEN** the system shall extract merchant name, purchase date, line items with quantities, and total amount

- **GIVEN** a receipt is from a supported vendor (Target, Amazon, Sprouts)
  - **WHEN** the system processes the receipt
  - **THEN** the system shall apply vendor-specific validation rules appropriate to that retailer's format

- **GIVEN** a Target receipt is being processed
  - **WHEN** the system extracts order information
  - **THEN** the system shall validate that order numbers match expected 15-digit patterns beginning with 902 or 912

- **GIVEN** a receipt image cannot be processed or parsed
  - **WHEN** extraction fails or confidence is below acceptable threshold
  - **THEN** the system shall flag the submission for manual review with reason code (unreadable image, unsupported format, or parsing failure)

- **GIVEN** a receipt is from a merchant not participating in the active campaign
  - **WHEN** the system validates merchant eligibility
  - **THEN** the system shall flag the submission for manual review with reason code indicating merchant mismatch

- **GIVEN** user identification data is extracted from submission
  - **WHEN** the system processes name and phone number fields
  - **THEN** the system shall normalize phone number formats and handle various name format variations

### Requirement 1.2: Campaign Validation & Product Matching

> **User Story:** As an operations team member, I want purchases automatically validated against campaign requirements so that only correct submissions are approved for payout.

**Requirements:**

- **GIVEN** campaign rules define required and optional product lists
  - **WHEN** the system validates extracted products against campaign requirements
  - **THEN** the system shall verify that all required products are present in the submission

- **GIVEN** OCR extraction may introduce variations in product names
  - **WHEN** the system matches extracted product names to campaign product lists
  - **THEN** the system shall use fuzzy matching with minimum 90% similarity threshold for product names while maintaining exact SKU validation

- **GIVEN** campaign rules define merchant, date range, quantity, and price criteria
  - **WHEN** the system validates a submission
  - **THEN** the system shall verify all criteria are met: eligible merchant, within campaign dates, correct quantities, and prices within acceptable ranges

- **GIVEN** all campaign validation rules are satisfied
  - **WHEN** the system completes verification checks
  - **THEN** the system shall mark the submission as "Verified" and route to fraud detection

- **GIVEN** one or more campaign rules are not satisfied
  - **WHEN** the system completes verification checks
  - **THEN** the system shall mark the submission as "Rejected" and record specific validation failures

- **GIVEN** extracted data is incomplete or ambiguous
  - **WHEN** the system cannot definitively verify or reject the submission
  - **THEN** the system shall flag the submission for manual review with details of incomplete data elements

### Requirement 1.3: Transaction Monitoring and Reporting

> **User Story:** As an operations/admin user, I want an Admin page to view all this fun stuff (all info and score) so that I can monitor transactions, scores, and system activity in one place.

**Requirements:**

- **GIVEN** an administrator needs to review system activity
  - **WHEN** the administrator accesses the monitoring interface
  - **THEN** the system shall provide access to submission records with verification status, fraud scores, and processing timestamps

- **GIVEN** an administrator needs to review transaction history
  - **WHEN** viewing historical data
  - **THEN** the system shall display submission details including approval status, payout information, and review decisions

- **GIVEN** an administrator needs to investigate flagged submissions
  - **WHEN** viewing submission details
  - **THEN** the system shall display verification results, fraud indicators, and risk scores with supporting evidence

- **GIVEN** an administrator needs to audit system decisions
  - **WHEN** reviewing processed submissions
  - **THEN** the system shall provide audit trail showing automated decisions, manual reviews, and decision rationale

---

## Use Case 2: Fraud Detection & Prevention

### Requirement 2.1: Duplicate Detection & Identity Fraud

> **User Story:** As an operations team member, I want to prevent users from submitting duplicate receipts or creating multiple accounts to avoid fraudulent payouts.

**Requirements:**

- **GIVEN** a receipt image is submitted for verification
  - **WHEN** the system checks for duplicate submissions
  - **THEN** the system shall compare the image against all previously submitted receipts and flag identical or near-identical matches

- **GIVEN** the system has processed submissions with order numbers
  - **WHEN** validating a new submission with an order number
  - **THEN** the system shall flag submissions where the same order number has been submitted by a different user

- **GIVEN** multiple users share the same phone number with different names
  - **WHEN** the system analyzes user profiles
  - **THEN** the system shall flag these accounts as potential duplicate or fraudulent identity patterns

- **GIVEN** user profile data appears incomplete or suspicious
  - **WHEN** the system evaluates account quality
  - **THEN** the system shall flag profiles with incomplete names (single letter, partial names), sequential phone numbers, or coordinated account creation patterns

- **GIVEN** duplicate submission or identity fraud is detected
  - **WHEN** the system identifies fraud indicators
  - **THEN** the system shall reject the submission, flag all related accounts, and alert operations team with evidence of fraud patterns

### Requirement 2.2: Risk Scoring & Pattern Analysis

> **User Story:** As an operations team member, I want to identify high-risk users and suspicious patterns before processing payouts so that we can prevent fraud losses.

**Requirements:**

- **GIVEN** the system needs to assess user fraud risk
  - **WHEN** evaluating a user or submission
  - **THEN** the system shall calculate a risk score based on profile completeness (full name vs. partial, verified contact information), phone format validity, submission timing patterns, and historical behavior

- **GIVEN** submission patterns may indicate coordinated fraud
  - **WHEN** the system analyzes submission data across users
  - **THEN** the system shall flag coordinated behavior including multiple users submitting identical products within the same 48-hour window

- **GIVEN** users may demonstrate systematic rule violations
  - **WHEN** the system reviews user history
  - **THEN** the system shall identify users who repeatedly fail validation checks or submit invalid data across more than 30% of their submissions

- **GIVEN** a user or submission exceeds risk thresholds
  - **WHEN** the risk score indicates high fraud probability
  - **THEN** the system shall require manual approval, hold payout processing, and log specific fraud evidence for audit review

- **GIVEN** a user demonstrates consistent compliant behavior
  - **WHEN** the system evaluates user history with no fraud indicators and successful submission rate above 90%
  - **THEN** the system shall assign lower risk scores to enable expedited processing

### Requirement 2.3: Identity Graph & Shadow Profiles

> **User Story:** As an operations team member, I want to identify users attempting to create multiple accounts to circumvent campaign limits so that we can prevent fraud across account networks.

**Requirements:**

- **GIVEN** the system collects device and network information from submissions
  - **WHEN** a user submits a receipt or interacts with the platform
  - **THEN** the system shall capture device identifiers and IP addresses for identity linking

- **GIVEN** multiple user accounts may be operated by the same individual
  - **WHEN** the system analyzes device and network patterns
  - **THEN** the system shall create shadow profiles linking accounts that share device IDs, IP addresses, or other identifying characteristics

- **GIVEN** shadow profiles indicate potential multi-account fraud
  - **WHEN** linked accounts collectively exceed campaign participation limits
  - **THEN** the system shall flag all linked accounts for review and prevent additional payouts pending investigation

- **GIVEN** legitimate users may share devices or networks (family members, shared workspaces)
  - **WHEN** shadow profiles are created
  - **THEN** the system shall allow manual override to mark linked accounts as legitimate separate individuals

### Requirement 2.4: Velocity Analysis & Behavioral Patterns

> **User Story:** As an operations team member, I want to detect unusual submission patterns that indicate fraud so that we can intervene before losses occur.

**Requirements:**

- **GIVEN** the system tracks submission frequency per user
  - **WHEN** analyzing user behavior
  - **THEN** the system shall calculate submission velocity (submissions per time period) and flag rates that exceed 3 submissions per 24-hour period

- **GIVEN** campaign rules define maximum participation limits
  - **WHEN** a user approaches or exceeds participation limits
  - **THEN** the system shall flag accounts attempting to exceed limits through rapid sequential submissions

- **GIVEN** the system tracks user reliability over time
  - **WHEN** evaluating a user's submission history
  - **THEN** the system shall maintain reliability score based on approval rate, compliance with requirements, and absence of fraud flags

- **GIVEN** velocity or reliability indicators suggest fraud
  - **WHEN** thresholds are exceeded
  - **THEN** the system shall escalate to manual review and temporarily suspend payout processing for the user

---

## Use Case 3: Customer Support Automation

### Requirement 3.1: Intent Classification & Automated Responses

> **User Story:** As a customer support team member, I want common user questions automatically classified and answered so that users get immediate help and I can focus on complex issues.

**Requirements:**

- **GIVEN** a user sends a message through SMS or mobile app chat
  - **WHEN** the system receives the message
  - **THEN** the system shall classify the message intent into defined categories: Payment Inquiry, Campaign Information, Technical Support, Account Verification, or General Inquiry

- **GIVEN** the message is classified as a common inquiry type
  - **WHEN** the system has sufficient information to provide an answer
  - **THEN** the system shall provide automated response using knowledge base information personalized with user-specific details (active campaigns, payout status, account state)

- **GIVEN** a user asks about specific campaign requirements
  - **WHEN** the system identifies campaign-related questions
  - **THEN** the system shall provide campaign-specific information including product requirements, submission instructions, and eligibility criteria

- **GIVEN** an automated response is provided to the user
  - **WHEN** the system sends the response
  - **THEN** the system shall maintain conversation context, log the interaction, and monitor for follow-up questions indicating unresolved issues

- **GIVEN** campaign information or knowledge base content is updated
  - **WHEN** content changes are made
  - **THEN** the system shall incorporate updated information into response generation within one business day

### Requirement 3.2: Human Handoff & Context Management

> **User Story:** As a customer support team member, I want complex queries escalated to me with full context so that I can provide effective help without asking users to repeat information.

**Requirements:**

- **GIVEN** an automated response does not resolve the user inquiry
  - **WHEN** the user continues to express dissatisfaction or asks follow-up questions
  - **THEN** the system shall escalate to human support with conversation history, user profile summary, and classification of issue type

- **GIVEN** technical issues or account problems are detected in user messages
  - **WHEN** the system identifies issues requiring human intervention
  - **THEN** the system shall route directly to human support without attempting automated resolution

- **GIVEN** a human support agent takes over a conversation
  - **WHEN** the handoff occurs
  - **THEN** the system shall notify the user of transition to human support, provide estimated response timeframe, and preserve complete conversation context

- **GIVEN** support agents mark certain query types for manual handling
  - **WHEN** these patterns are identified in future conversations
  - **THEN** the system shall route similar queries directly to human support based on learned patterns

- **GIVEN** the knowledge base lacks information to answer a query
  - **WHEN** the system cannot provide confident automated response
  - **THEN** the system shall escalate to human support with context rather than providing incomplete or uncertain information

### Requirement 3.3: Multi-Channel Support Integration

> **User Story:** As a developer/stakeholder, I want a chatbot UI library-like component for integration on mobile so that customer support chat can be embedded consistently in the mobile app.

**Requirements:**

- **GIVEN** customer support functionality needs to be accessible in multiple channels
  - **WHEN** users interact through mobile app or web interface
  - **THEN** the system shall provide consistent support experience across all channels with unified conversation history

- **GIVEN** the mobile application requires embedded chat functionality
  - **WHEN** integrating support features into the mobile app
  - **THEN** the system shall provide reusable chat components that can be embedded into the mobile application interface

- **GIVEN** conversations may span multiple sessions and channels
  - **WHEN** a user returns to continue a conversation
  - **THEN** the system shall maintain context and history regardless of which channel the user accesses

---

## Data Requirements

**Data Sources:**

- **User Profiles (CMS):** names, emails, phone numbers, social media handles, approval status, verification history, geographic location, timezone, device identifiers, IP address history
- **Campaigns (CSV/Config):** active campaign rules, required SKUs, price ranges, quantities, date ranges, participating merchants, payout amounts, completion requirements, historical performance, fraud patterns
- **Transactions (S3/Dots):** complete message history with timestamps, receipt submission history, approval/rejection decisions, payment processing history, device and network metadata
- **Audit Data:** manual review decisions and reasoning, fraud flags, investigation outcomes, pattern analysis from previous cases, system decision logs, confidence scores

**Integration Points:**

- **CMS Database:** read access to backend database, message history extraction with full conversation threads, user profile synchronization
- **Mobile Application:** real-time data sync with mobile app backend via S3, receipt image upload and processing pipeline, chat interface integration for support conversations
- **External APIs:** Dots payment platform (transaction history and payout data), CSV campaign files (rules and completion tracking)

---


## Specification Format

Requirements follow spec-driven development: **GIVEN** [preconditions] **WHEN** [trigger] **THEN** [expected behavior]

All requirements are testable, measurable, traceable to business needs, and technology-agnostic.
