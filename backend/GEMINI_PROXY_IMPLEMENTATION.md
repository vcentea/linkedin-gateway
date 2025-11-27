# Gemini AI Proxy Implementation Plan

## Overview
Implement a Gemini AI proxy that allows users to authenticate with their Google account via OAuth 2.0 and access Gemini models through OpenAI-compatible and native Gemini API endpoints.

## Reference Implementation
Based on [geminicli2api](https://github.com/gzzhongqi/geminicli2api) - uses Google's public Gemini CLI OAuth credentials.

## Implementation Status Legend
- [ ] Not started
- [🔄] In progress
- [✅] Completed
- [⏸️] Blocked/Waiting

---

## Phase 1: Database & Backend Foundation

### 1.1 Database Migration
**Priority:** Critical (blocks everything)
**Dependencies:** None

- [✅] **Task 1.1.1**: Create migration file `alembic/versions/add_gemini_credentials_to_api_keys.py`
  - Add `gemini_credentials` JSONB column to `api_keys` table
  - Use `add_column_if_not_exists` helper for idempotency
  - Include proper downgrade function

- [✅] **Task 1.1.2**: Update `app/db/models/api_key.py`
  - Add `gemini_credentials = Column(JSONB, default={})`
  - Add comment explaining the credential structure

### 1.2 Backend Schemas
**Priority:** High
**Dependencies:** 1.1

- [✅] **Task 1.2.1**: Create `app/schemas/gemini.py`
  - Define `GeminiCredentials` schema (client_id, client_secret, token, refresh_token, scopes, token_uri, expiry, project_id)
  - Define `GeminiCredentialsUpdate` schema for PATCH endpoint
  - Define `ChatCompletionRequest` (OpenAI-compatible)
  - Define `ChatCompletionResponse` (OpenAI-compatible)
  - Define `GeminiGenerateContentRequest` (native)
  - Define `GeminiGenerateContentResponse` (native)

### 1.3 Backend Credential Management Endpoints
**Priority:** High
**Dependencies:** 1.1, 1.2

- [ ] **Task 1.3.1**: Add endpoint in `app/user/api_key.py`
  - `PATCH /users/me/api-key/gemini-credentials` - Update Gemini OAuth credentials
  - Use same auth pattern as `csrf-token` and `linkedin-cookies` endpoints
  - Validate credential structure before saving

- [ ] **Task 1.3.2**: Update `app/schemas/api_key.py` (if exists) or create
  - Add Gemini credential fields to API key response schema

---

## Phase 2: Gemini Service Module (Backend)

### 2.1 Gemini Module Structure
**Priority:** High
**Dependencies:** 1.1, 1.2

- [ ] **Task 2.1.1**: Create `app/gemini/__init__.py`
  - Module initialization

- [ ] **Task 2.1.2**: Create `app/gemini/config.py`
  - Define constants:
    - `GEMINI_CLIENT_ID` (from Gemini CLI)
    - `GEMINI_CLIENT_SECRET` (from Gemini CLI)
    - `GEMINI_SCOPES`
    - `CODE_ASSIST_ENDPOINT`
    - `DEFAULT_SAFETY_SETTINGS`
    - `SUPPORTED_MODELS` list

- [ ] **Task 2.1.3**: Create `app/gemini/auth.py`
  - `get_credentials_from_json(credentials_json: dict)` - Parse credentials
  - `refresh_credentials_if_expired(credentials)` - Token refresh logic
  - `save_refreshed_credentials(db, api_key_id, new_credentials)` - Update DB
  - Use `google-auth` library for credential handling

- [ ] **Task 2.1.4**: Create `app/gemini/helpers.py`
  - `get_gemini_service(db, api_key, service_class)` - Factory function (similar to LinkedIn pattern)
  - `build_request_headers(access_token)` - Build auth headers
  - `get_user_agent()` - CLI-compatible user agent

### 2.2 Gemini Chat Service
**Priority:** High
**Dependencies:** 2.1

- [ ] **Task 2.2.1**: Create `app/gemini/services/__init__.py`

- [ ] **Task 2.2.2**: Create `app/gemini/services/chat.py`
  - `GeminiChatService` class
  - `generate_content(model, contents, generation_config)` - Non-streaming
  - `stream_generate_content(model, contents, generation_config)` - Streaming
  - `_make_request(endpoint, payload, stream)` - Internal request handler
  - Handle both server-side and proxy modes (consistent with LinkedIn pattern)

---

## Phase 3: API Endpoints (Backend)

### 3.1 OpenAI-Compatible Endpoint
**Priority:** High
**Dependencies:** 2.2

- [ ] **Task 3.1.1**: Create `app/api/v1/gemini_chat.py`
  - `POST /chat/completions` - OpenAI-compatible chat completions
  - Support streaming via SSE
  - Transform OpenAI format → Gemini format → OpenAI format
  - Use same API key auth as LinkedIn endpoints (`validate_api_key_from_header_or_body`)

- [ ] **Task 3.1.2**: Create `app/api/v1/gemini_models.py`
  - `GET /models` - List available Gemini models (OpenAI format)

### 3.2 Native Gemini Endpoints
**Priority:** Medium
**Dependencies:** 2.2

- [ ] **Task 3.2.1**: Create `app/api/v1/gemini_native.py`
  - `GET /gemini/models` - List Gemini models (native format)
  - `POST /gemini/models/{model}:generateContent` - Generate content
  - `POST /gemini/models/{model}:streamGenerateContent` - Stream content
  - Direct pass-through to Gemini API

### 3.3 Router Registration
**Priority:** High
**Dependencies:** 3.1, 3.2

- [ ] **Task 3.3.1**: Update `main.py`
  - Import Gemini routers
  - Register with appropriate prefixes:
    - `gemini_chat_router` at `/api/v1`
    - `gemini_models_router` at `/api/v1`
    - `gemini_native_router` at `/api/v1`

---

## Phase 4: Extension - Constants & Configuration

### 4.1 Message Types & Constants
**Priority:** High
**Dependencies:** None (can be done in parallel with backend)

- [ ] **Task 4.1.1**: Update `src-v2/shared/constants/message-types.js`
  - Add `CHECK_GEMINI_AUTH`
  - Add `START_GEMINI_OAUTH`
  - Add `GET_GEMINI_STATUS`
  - Add `GEMINI_STATUS_UPDATE`
  - Add `UPDATE_GEMINI_CREDENTIALS`

- [ ] **Task 4.1.2**: Create `src-v2/shared/constants/gemini-constants.js`
  - `GEMINI_CLIENT_ID`
  - `GEMINI_SCOPES`
  - `GEMINI_AUTH_URL`
  - `GEMINI_TOKEN_URL`
  - Cookie/storage key names

### 4.2 Manifest Update
**Priority:** Critical
**Dependencies:** None

- [ ] **Task 4.2.1**: Update `manifest.json`
  - Add `"identity"` permission for OAuth flow
  - Add `"https://accounts.google.com/*"` to permissions if needed
  - Add `"https://oauth2.googleapis.com/*"` to permissions

---

## Phase 5: Extension - Background Service

### 5.1 Gemini Controller
**Priority:** High
**Dependencies:** 4.1, 4.2

- [ ] **Task 5.1.1**: Create `src-v2/background/controllers/gemini.controller.js`
  - `init()` - Initialize controller
  - `handleMessage(message, sendResponse)` - Message router
  - `startOAuthFlow()` - Launch OAuth web auth flow
  - `exchangeCodeForTokens(authCode)` - Exchange code for tokens
  - `checkGeminiStatus()` - Verify credentials are valid
  - `refreshTokensIfNeeded()` - Automatic token refresh
  - `getGeminiCredentials()` - Get stored credentials
  - `saveGeminiCredentials(credentials)` - Save to storage

### 5.2 Background Index Update
**Priority:** High
**Dependencies:** 5.1

- [ ] **Task 5.2.1**: Update `src-v2/background/index.js`
  - Import `gemini.controller.js`
  - Call `geminiController.init()` on startup
  - Add Gemini message handling to main message router

### 5.3 Auth Service Extension
**Priority:** High
**Dependencies:** 5.1

- [ ] **Task 5.3.1**: Update `src-v2/background/services/auth.service.js`
  - Add `updateGeminiCredentials(credentials)` function
  - Add `getGeminiCredentials()` function
  - Reuse existing patterns from LinkedIn credential updates

---

## Phase 6: Extension - Shared API Layer

### 6.1 API Functions
**Priority:** High
**Dependencies:** 1.3

- [ ] **Task 6.1.1**: Update `src-v2/shared/api/index.js`
  - Add `updateGeminiCredentials(accessToken, credentials)` function
  - Follow same pattern as `updateLinkedInCookies()`

---

## Phase 7: Extension - Dashboard UI

### 7.1 Gemini Status Component
**Priority:** High
**Dependencies:** 5.1, 6.1

- [ ] **Task 7.1.1**: Create `src-v2/pages/components/dashboard/GeminiStatus.js`
  - Copy structure from `LinkedInStatus.js`
  - Adapt for Gemini OAuth flow
  - `checkGeminiStatus()` - Check if credentials exist and valid
  - `startOAuthFlow()` - Initiate Google OAuth
  - `updateStatusDisplay(isConnected)` - Update UI
  - Use same timer/interval pattern as LinkedIn
  - Handle token refresh on visibility change

### 7.2 Dashboard HTML Update
**Priority:** High
**Dependencies:** 7.1

- [ ] **Task 7.2.1**: Update `src-v2/pages/dashboard/index.html`
  - Add Gemini status row in "Services Availability" section
  - Add `gemini-status-message` span
  - Add `gemini-connect-btn` button
  - Style consistently with LinkedIn section

### 7.3 Dashboard JS Update
**Priority:** High
**Dependencies:** 7.1, 7.2

- [ ] **Task 7.3.1**: Update `src-v2/pages/dashboard/index.js`
  - Import `GeminiStatus` component
  - Initialize in `displayDashboard()`

---

## Phase 8: Storage Service

### 8.1 Storage for Gemini Credentials
**Priority:** High
**Dependencies:** 4.1

- [ ] **Task 8.1.1**: Update `src-v2/background/services/storage.service.js`
  - Add `saveGeminiCredentials(credentials)` function
  - Add `getGeminiCredentials()` function
  - Add `clearGeminiCredentials()` function
  - Use per-server storage pattern (like auth data)

---

## Phase 9: Backend Dependencies

### 9.1 Python Dependencies
**Priority:** Critical (blocks Phase 2)
**Dependencies:** None

- [✅] **Task 9.1.1**: Update `requirements/base.txt` or `requirements.txt`
  - Add `google-auth>=2.29.0`
  - Add `google-auth-oauthlib>=1.2.0`
  - ~~Add `google-auth-httplib2>=0.1.0` (if needed)~~ - Not needed

---

## Phase 10: Testing & Verification

### 10.1 Backend Testing
**Priority:** High
**Dependencies:** Phase 1-3

- [ ] **Task 10.1.1**: Test database migration
  - Run migration on dev database
  - Verify column created correctly
  - Test rollback

- [ ] **Task 10.1.2**: Test credential update endpoint
  - Test with valid credentials
  - Test with invalid credentials
  - Test authentication requirements

- [ ] **Task 10.1.3**: Test chat completions endpoint
  - Test non-streaming response
  - Test streaming response
  - Test error handling

### 10.2 Extension Testing
**Priority:** High
**Dependencies:** Phase 4-8

- [ ] **Task 10.2.1**: Test OAuth flow
  - Verify Google consent screen appears
  - Verify tokens received
  - Verify tokens stored correctly

- [ ] **Task 10.2.2**: Test credential sync
  - Verify credentials sent to backend
  - Verify status updates correctly

- [ ] **Task 10.2.3**: Test token refresh
  - Verify automatic refresh works
  - Verify UI updates after refresh

---

## File Summary

### New Files to Create (16 files)

**Backend (11 files):**
1. `alembic/versions/add_gemini_credentials_to_api_keys.py`
2. `app/schemas/gemini.py`
3. `app/gemini/__init__.py`
4. `app/gemini/config.py`
5. `app/gemini/auth.py`
6. `app/gemini/helpers.py`
7. `app/gemini/services/__init__.py`
8. `app/gemini/services/chat.py`
9. `app/api/v1/gemini_chat.py`
10. `app/api/v1/gemini_models.py`
11. `app/api/v1/gemini_native.py`

**Extension (2 files):**
1. `src-v2/shared/constants/gemini-constants.js`
2. `src-v2/pages/components/dashboard/GeminiStatus.js`
3. `src-v2/background/controllers/gemini.controller.js`

### Files to Modify (10 files)

**Backend (3 files):**
1. `app/db/models/api_key.py` - Add gemini_credentials column
2. `app/user/api_key.py` - Add PATCH endpoint
3. `main.py` - Register routers

**Extension (7 files):**
1. `manifest.json` - Add identity permission
2. `src-v2/shared/constants/message-types.js` - Add Gemini message types
3. `src-v2/shared/api/index.js` - Add API function
4. `src-v2/background/index.js` - Initialize Gemini controller
5. `src-v2/background/services/auth.service.js` - Add Gemini functions
6. `src-v2/background/services/storage.service.js` - Add Gemini storage
7. `src-v2/pages/dashboard/index.html` - Add UI elements
8. `src-v2/pages/dashboard/index.js` - Initialize component

---

## Implementation Order (Recommended)

```
Phase 9 (Dependencies) → Phase 1 (Database) → Phase 2 (Gemini Module) → Phase 3 (API Endpoints)
                                    ↓
Phase 4 (Constants) → Phase 5 (Background) → Phase 6 (API Layer) → Phase 7 (Dashboard) → Phase 8 (Storage)
                                    ↓
                            Phase 10 (Testing)
```

**Parallel Work Possible:**
- Backend (Phase 1-3) and Extension Constants (Phase 4) can be done in parallel
- Extension work (Phase 5-8) requires Phase 4 complete

---

## Notes

1. **Reuse Patterns**: Follow existing LinkedIn patterns for consistency
2. **No Code Duplication**: Extract shared logic into helpers
3. **Minimal Changes**: Only modify what's necessary
4. **Clean Separation**: All Gemini code in dedicated files/folders
5. **Error Handling**: Robust error handling at all layers
6. **Logging**: Consistent logging for debugging

---

## Last Updated
Date: 2025-11-26
Status: **IMPLEMENTATION COMPLETE** ✅

## Implementation Summary

### Backend Files Created (11 files)
1. ✅ `alembic/versions/add_gemini_credentials_to_api_keys.py` - DB migration
2. ✅ `app/schemas/gemini.py` - Request/response schemas
3. ✅ `app/gemini/__init__.py` - Module init
4. ✅ `app/gemini/config.py` - Constants and config
5. ✅ `app/gemini/auth.py` - OAuth credential handling
6. ✅ `app/gemini/helpers.py` - Utility functions
7. ✅ `app/gemini/services/__init__.py` - Services module init
8. ✅ `app/gemini/services/chat.py` - Chat completion service
9. ✅ `app/api/v1/gemini_chat.py` - OpenAI-compatible endpoint
10. ✅ `app/api/v1/gemini_models.py` - Models listing endpoint
11. ✅ `app/api/v1/gemini_native.py` - Native Gemini endpoints

### Backend Files Modified (5 files)
1. ✅ `requirements/base.txt` - Added google-auth dependencies
2. ✅ `app/db/models/api_key.py` - Added gemini_credentials column
3. ✅ `app/schemas/api_key.py` - Added Gemini credential schemas
4. ✅ `app/crud/api_key.py` - Added Gemini CRUD functions
5. ✅ `app/user/api_key.py` - Added PATCH endpoint
6. ✅ `main.py` - Registered Gemini routers

### Extension Files Created (3 files)
1. ✅ `src-v2/shared/constants/gemini-constants.js` - OAuth constants
2. ✅ `src-v2/background/controllers/gemini.controller.js` - Background controller
3. ✅ `src-v2/pages/components/dashboard/GeminiStatus.js` - UI component

### Extension Files Modified (7 files)
1. ✅ `manifest.json` - Added identity permission
2. ✅ `src-v2/shared/constants/message-types.js` - Added Gemini messages
3. ✅ `src-v2/shared/api/index.js` - Added updateGeminiCredentials
4. ✅ `src-v2/background/index.js` - Registered Gemini controller
5. ✅ `src-v2/background/services/auth.service.js` - Added Gemini update function
6. ✅ `src-v2/pages/dashboard/index.html` - Added Gemini UI section
7. ✅ `src-v2/pages/dashboard/index.js` - Initialized GeminiStatus

### API Endpoints Created
- `POST /api/v1/chat/completions` - OpenAI-compatible chat
- `GET /api/v1/models` - List available models
- `GET /api/v1/models/{model_id}` - Get model details
- `GET /api/v1/gemini/models` - Native model list
- `POST /api/v1/gemini/models/{model}:generateContent` - Native generate
- `POST /api/v1/gemini/models/{model}:streamGenerateContent` - Native stream
- `PATCH /users/me/api-key/gemini-credentials` - Update credentials

## Next Steps for Testing
1. Run database migration: `alembic upgrade head`
2. Install new dependencies: `pip install -r requirements/base.txt`
3. Build extension: `npm run build`
4. Load extension in Chrome
5. Test OAuth flow via extension
6. Test API endpoints with authenticated credentials

