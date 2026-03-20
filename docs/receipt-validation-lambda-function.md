# `lambdas/devyansh-lambda` Receipt Validation Documentation

## What this lambda does
`lambdas/devyansh-lambda/lambda_handler.py` is a Chatwoot webhook handler for receipt/proof validation.

Given a Chatwoot webhook payload containing an image attachment (receipt, review screenshot, selfie, etc.), it:
1. Extracts the image bytes (by fetching the Chatwoot `data_url`)
2. Computes a content hash (`image_hash`) and writes the image to `/tmp`
3. Runs a LangGraph “receipt verification” workflow
4. Writes a reply message back to the Chatwoot conversation

It currently uses the compiled 4-node “proof pipeline” graph from `workflow.get_compiled_graph_proof()`.

## Webhook entrypoint and Chatwoot I/O
Entry file: `lambdas/devyansh-lambda/lambda_handler.py`

### 1) Parse Chatwoot event
The handler expects a Chatwoot-style webhook body and parses it from:
- `event["body"]` (JSON string) OR a dict body

Helper functions:
- `_parse_chatwoot_event(event)`: safe JSON parsing
- `_get_chatwoot_attachments(data)`: reads `attachments` either at the top-level payload or under the last conversation message

### 2) Find the image attachment and fetch bytes
The image attachment is recognized by:
- `attachment["file_type"]` == `"image"`, OR
- presence of `attachment["data_url"]`

Image fetching:
- `_fetch_image_from_url(url, chatwoot_host)` replaces `0.0.0.0` with `CHATWOOT_IMAGE_HOST`
- It fetches bytes from the final URL

Then:
- `_get_image_and_context_from_chatwoot(...)` returns:
  - `image_b64` (base64 string)
  - `user_id` (from `sender.id`, else sender.email, else contact_inbox.contact_id)
  - `campaign_id` (from `custom_attributes.campaign_id`)
  - `chatwoot_reply_context` containing `{account_id, conversation_id}`

### 3) Decode/validate image and prepare for pipeline
The handler decodes base64 and enforces size constraints:
- `MIN_IMAGE_BYTES = 100`
- `MAX_IMAGE_BYTES = 20 * 1024 * 1024` (20MB)

It computes:
- `image_hash = sha256(image_bytes).hexdigest()`

It writes a local file in `/tmp` via `_decode_image_and_prepare_file(...)` and stores:
- `receipt_file_path`
- `image_hash`

### 4) Build initial LangGraph state (`AIEngineState`)
It builds the initial state with `_build_initial_state_proof(...)`, which includes:
- input fields:
  - `receipt_file_path`, `image_hash`, `user_id`, `campaign_id`, `conversation_id`
  - `submission_timestamp`
- error/audit fields:
  - `input_validation_errors`, `extraction_errors`, `violation_details`
- bypass flag:
  - `bypass_validation = BYPASS_VALIDATION` (from env)
- proof session fields (if loaded):
  - `proof_session_id`, `submitted_proofs`, `required_proof_types`

If session document exists, it is loaded using:
- `services.mongodb_campaigns.proof_session_get(...)`

### 5) Send typing indicator + run graph + send reply
It toggles typing on/off with `_chatwoot_toggle_typing(...)`.

Graph invocation:
- `graph = workflow.get_compiled_graph_proof()`
- `final_state = graph.invoke(initial_state)`

Reply formatting:
- if `final_state["reply_message"]` exists, handler sends it directly
- otherwise it formats a reply using `_format_chatwoot_reply_message(final_state)`

It then builds a slim response body (`_build_response`) and returns it to the Lambda runtime.

## Receipt verification LangGraph workflows
All LangGraph logic is in:
`lambdas/devyansh-lambda/workflow.py`

## Graph 1 (legacy): extraction + validation (not the active one)
Legacy described in file docstring and implemented by `build_graph()`:

Start -> `input_s3_duplicate` -> conditional:
- If `is_duplicate` -> END
- Else if `input_validation_status != "valid"` -> END
- Else -> `extraction`

Then -> conditional:
- If `bypass_validation` -> `validation_bypass`
- Else -> `validation`

Finally:
- `validation` -> END
- `validation_bypass` -> END

Graph 1 nodes:
- `node_input_s3_duplicate` (steps: `step1_input_s3_duplicate.py`)
- `node_extraction` (steps: `step2_extraction.py` using Document AI + Bedrock fallback)
- `node_validation` (steps: `step3_validation.py`)
- `node_validation_bypass`

## Graph 2 (active): the 4-node “proof pipeline”
Graph 2 is implemented by `build_proof_graph()` and compiled by `get_compiled_graph_proof()`.

Control-flow:
START -> `get_mongo` -> conditional:
- If `is_duplicate` -> `update_mongo` -> END
- Else -> `detect_image`

Then conditional after `detect_image`:
- If `is_valid_image` is False -> `update_mongo` -> END
- Else -> `validation`

Finally:
- `validation` -> `update_mongo` -> END

Node list:
- `node_get_mongo` (read-only)
- `node_detect_image` (Bedrock VLM detect+fraud+extraction)
- `node_validation` (step3_validation)
- `node_update_mongo` (writes: S3 + DB history + proof session)

## State schema: `AIEngineState`
Defined in `lambdas/devyansh-lambda/state.py`.

Key fields used by Graph 2:
- inputs:
  - `receipt_file_path`, `image_hash`, `user_id`, `campaign_id`, `conversation_id`
  - `bypass_validation`
- get_mongo outputs:
  - `is_duplicate`, `reply_message` (duplicate reply), `campaign_rules`, `required_proof_types`, `submitted_proofs`
- detect_image outputs:
  - `detected_image_type`, `is_valid_image`, `extraction_confidence` (via flattened fields), `merchant_name`, `purchase_date`, `order_number`, `total_amount`, `extracted_data`, etc.
- validation outputs:
  - `final_decision`, `validation_status`, `validation_score`, `requires_manual_review`, `review_reason`, `reply_message`
- update_mongo side effects:
  - sets `receipt_s3_bucket`, `receipt_s3_key` when upload succeeds

## Node-by-node behavior (Graph 2)

### Node A: `node_get_mongo` (read-only)
Location: `lambdas/devyansh-lambda/nodes/node_get_mongo.py`

Responsibilities:
1. Duplicate check:
   - calls `services.mongodb_campaigns.receipt_hash_exists(MONGODB_URI, receipt_hash_collection, image_hash)`
   - if duplicate:
     - sets `out["is_duplicate"]=True`
     - sets `out["reply_message"]="This image has already been submitted."`
     - returns early
2. Load user (optional):
   - calls `services.mongodb_campaigns.get_user(user_id, ...)`
3. Load campaign rules (optional):
   - calls `services.mongodb_campaigns.get_campaign_rules(campaign_id, ...)`
   - also sets `required_proof_types` from rules
4. Load proof session for multi-proof:
   - calls `services.mongodb_campaigns.proof_session_get(...)`
   - if found: loads `submitted_proofs` + `required_proof_types`

### Node B: `node_detect_image` (fraud/validity + extraction)
Location: `lambdas/devyansh-lambda/nodes/node_detect_image.py`

Responsibilities:
1. Delegates to `steps/step_detect_image.py: run_detect_image(state)`
2. That step calls:
   - `services.bedrock_vlm.detect_image_type_fraud_extract(...)`

Important characteristics:
- It uses ONE Bedrock VLM call to do:
  - image type classification: `order_receipt` | `order_id` | `review` | `selfie`
  - fraud/validity check with `validity_confidence_threshold`
  - type-specific extraction

Outputs written to state:
- `detected_image_type`
- `is_valid_image` (only true if validity confidence meets threshold)
- `validity_confidence`
- `detection_rejection_reason` (if invalid)
- `extracted_data` (type-specific extraction result)
- flattened extraction fields used by validation:
  - `merchant_name`, `purchase_date`, `order_number`, `total_amount`, `line_items`, `extraction_confidence`

If image invalid:
- sets `reply_message` (either generic invalid message or `detection_rejection_reason`)

### Node C: `node_validation` (MongoDB-based validation)
Location: `lambdas/devyansh-lambda/nodes/node_validation.py`

Behavior:
1. Checks multi-proof pending state:
   - `steps/step3_validation._check_multiproof_pending(state)`
   - if campaign requires multiple proof types and pending exists:
     - returns an update that sets:
       - `submitted_proofs`
       - `pending_proof_types`
       - `reply_message` instructing user which proof to upload next
2. Otherwise runs full validation:
   - `steps/step3_validation.py: run_validation(state)`

Full validation responsibilities inside `run_validation`:
1. Extraction presence check:
   - if `extracted_data` missing -> immediately fail
2. Resolve campaign:
   - `services.mongodb_campaigns.find_crwd_by_merchant_name(...)` fuzzy matches `merchant_name` to active campaigns
3. Enforce campaign constraints:
   - campaign must be Active and not deleted
   - purchase date must be within campaign date_range
   - campaign type_of_work_proof must accept `order_receipt`
4. Enforce user constraints:
   - user exists
   - user is Active
   - user not blocked (`is_user_blocked`)
   - user is a campaign member (`is_worker_in_campaign`)
5. Enforce receipt content constraints:
   - loads validation rules (`get_campaign_rules`)
   - validates:
     - merchant validity (optional)
     - products:
       - preferred path: gig_stores + store products validation
       - fallback path: legacy required/optional products validation
     - vendor-specific rules (e.g. Target order number pattern)
     - optional order number reuse:
       - `order_number_used_in_campaign(...)`
6. Compute decision:
   - `_calculate_validation_score(validation_results)` and `_determine_final_decision(...)`
   - sets:
     - `final_decision`: `APPROVED` | `REJECTED` | `PENDING_REVIEW`
     - `validation_status`: `verified` | `rejected` | `pending_review`
     - `requires_manual_review`, `review_reason`
     - `reply_message` for Chatwoot
   - writes an audit trail

### Node D: `node_update_mongo` (writes + uploads)
Location: `lambdas/devyansh-lambda/nodes/node_update_mongo.py`

Responsibilities:
1. Optional S3 upload + receipt hash insert:
   - uploads from `state["receipt_file_path"]` into:
     - `receipts/{user_id}/{timestamp}_{uuid}.{jpg|png}`
   - calls:
     - `services.s3.upload_receipt(...)`
     - `services.mongodb_campaigns.receipt_hash_insert(...)`
   - skips when:
     - `is_duplicate == True`
     - `BYPASS_S3_UPLOAD == True`
2. Always attempts receipt upload history insert (if Mongo configured):
   - `services.mongodb_campaigns.receipt_upload_history_insert(...)`
   - status computed from `state["final_decision"]`:
     - pass if `APPROVED`, else fail
   - stores:
     - `receipt_s3_key`, `violation_details`, `validation_results`
     - `matched_store` (store_id/store_name + matched_products) when available
     - `extracted_data` (merchant/date/order/amount/confidence)
3. Multi-proof session persistence:
   - if there is `required_proof_types`:
     - if `pending_proof_types` exists -> `proof_session_upsert(...)`
     - if final decision is Approved/Rejected -> `proof_session_delete(...)`

## Key “tools” / integration points used by Graph 2
This lambda does not use LangChain tools; instead it uses explicit service calls from nodes/steps:

### LLM/Vision
- `services.bedrock_vlm.detect_image_type_fraud_extract(...)`
  - Bedrock VLM one-call detect+fraud+extraction for the 4 proof types
- (Legacy extraction) `services.document_ai.extract_receipt(...)` + fallback:
  - `services.bedrock_vlm.extract_receipt_with_fraud_check(...)`

### MongoDB reads/writes
Mongo calls are centralized in `services/mongodb_campaigns.py`, including:
- duplicate hash check:
  - `receipt_hash_exists(...)`
- proof session:
  - `proof_session_get(...)`, `proof_session_upsert(...)`, `proof_session_delete(...)`
- receipt upload history:
  - `receipt_upload_history_insert(...)`
- rules & membership checks:
  - `get_campaign_rules(...)`, `find_crwd_by_merchant_name(...)`,
  - `get_user(...)`, `is_user_blocked(...)`, `is_worker_in_campaign(...)`,
  - `order_number_used_in_campaign(...)`

### S3
- `services.s3.upload_receipt(...)`

### Duplicate detection
Two implementations exist:
- Mongo-backed receipt hash:
  - `receipt_hash_exists(...)`
  - `receipt_hash_insert(...)`
- DynamoDB-backed hash check (used in legacy step1):
  - `steps.step1_input_s3_duplicate` uses `services.duplicate_check.check_duplicate(...)`

## Summary: Graph transition logic (Graph 2)
1. `get_mongo` decides:
   - if duplicate -> skip detection+validation and write history via `update_mongo`
   - else -> run detection/extraction
2. `detect_image` decides:
   - if invalid proof image -> write fail history via `update_mongo`
   - else -> validate against campaign rules and membership via `validation`
3. `validation` always ends with `update_mongo` to persist receipt history and proof-session progress.

