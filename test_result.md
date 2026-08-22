#====================================================================================================
# START - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================

# THIS SECTION CONTAINS CRITICAL TESTING INSTRUCTIONS FOR BOTH AGENTS
# BOTH MAIN_AGENT AND TESTING_AGENT MUST PRESERVE THIS ENTIRE BLOCK

# Communication Protocol:
# If the `testing_agent` is available, main agent should delegate all testing tasks to it.
#
# You have access to a file called `test_result.md`. This file contains the complete testing state
# and history, and is the primary means of communication between main and the testing agent.
#
# Main and testing agents must follow this exact format to maintain testing data. 
# The testing data must be entered in yaml format Below is the data structure:
# 
## user_problem_statement: {problem_statement}
## backend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.py"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## frontend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.js"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## metadata:
##   created_by: "main_agent"
##   version: "1.0"
##   test_sequence: 0
##   run_ui: false
##
## test_plan:
##   current_focus:
##     - "Task name 1"
##     - "Task name 2"
##   stuck_tasks:
##     - "Task name with persistent issues"
##   test_all: false
##   test_priority: "high_first"  # or "sequential" or "stuck_first"
##
## agent_communication:
##     -agent: "main"  # or "testing" or "user"
##     -message: "Communication message between agents"

# Protocol Guidelines for Main agent
#
# 1. Update Test Result File Before Testing:
#    - Main agent must always update the `test_result.md` file before calling the testing agent
#    - Add implementation details to the status_history
#    - Set `needs_retesting` to true for tasks that need testing
#    - Update the `test_plan` section to guide testing priorities
#    - Add a message to `agent_communication` explaining what you've done
#
# 2. Incorporate User Feedback:
#    - When a user provides feedback that something is or isn't working, add this information to the relevant task's status_history
#    - Update the working status based on user feedback
#    - If a user reports an issue with a task that was marked as working, increment the stuck_count
#    - Whenever user reports issue in the app, if we have testing agent and task_result.md file so find the appropriate task for that and append in status_history of that task to contain the user concern and problem as well 
#
# 3. Track Stuck Tasks:
#    - Monitor which tasks have high stuck_count values or where you are fixing same issue again and again, analyze that when you read task_result.md
#    - For persistent issues, use websearch tool to find solutions
#    - Pay special attention to tasks in the stuck_tasks list
#    - When you fix an issue with a stuck task, don't reset the stuck_count until the testing agent confirms it's working
#
# 4. Provide Context to Testing Agent:
#    - When calling the testing agent, provide clear instructions about:
#      - Which tasks need testing (reference the test_plan)
#      - Any authentication details or configuration needed
#      - Specific test scenarios to focus on
#      - Any known issues or edge cases to verify
#
# 5. Call the testing agent with specific instructions referring to test_result.md
#
# IMPORTANT: Main agent must ALWAYS update test_result.md BEFORE calling the testing agent, as it relies on this file to understand what to test next.

#====================================================================================================
# END - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================


#====================================================================================================
# Testing Data - reconciled 2026-08-22
#====================================================================================================

## user_problem_statement: "Production-readiness hardening and build verification for TrackMyRMC before isolated preview deployment."

## backend:
##   - task: "Full FastAPI/Mongo regression and production-hardening suite"
##     implemented: true
##     working: true
##     file: "backend/tests/"
##     stuck_count: 0
##     priority: "high"
##     needs_retesting: false
##     status_history:
##       - working: true
##         agent: "main"
##         comment: "GitHub Production Readiness executed the full Mongo-backed suite serially: 154 passed, 2 skipped, 0 failed. FastAPI boot and /api/health also passed."
##
##   - task: "PREVIEW boot verification: backend /api/health, Mongo connectivity, dev OTP login flow"
##     implemented: true
##     working: true
##     file: "backend/server.py, backend/routers/auth.py"
##     stuck_count: 0
##     priority: "high"
##     needs_retesting: false
##     status_history:
##       - working: true
##         agent: "testing"
##         comment: "PREVIEW boot verification PASSED (5/5 checks): 1) GET /api/health returns 200 with status='healthy' and notifications.configured=false (SMS/email unconfigured as expected). 2) GET /api/ returns 200. 3) MongoDB connectivity confirmed - backend successfully reads/writes OTP documents. 4) Dev OTP login flow with Customer (+919000000001): request-otp returns 200 with dev_otp=690778 and delivery.configured=false (no real SMS sent), verify-otp returns 200 with access_token, role='customer', name='Rajesh Kumar'. 5) Dev OTP login flow with Plant Owner (owner@trackmyrmc.test): request-otp returns 200 with dev_otp=130469 and delivery.configured=false (no real email sent), verify-otp returns 200 with access_token, role='plant_owner', name='Concrete King (Owner)'. All 13 demo users seeded successfully. Rate limiting working correctly (429 response when requesting OTP too quickly). Backend logs confirm [NOT_CONFIGURED] for SMS/email delivery. No code, .env, or dependency modifications made."
##
##   - task: "10 staff role dashboards, plant scoping and non-staff RBAC"
##     implemented: true
##     working: true
##     file: "backend/routers/staff.py, backend/tests/test_staff_dashboards.py"
##     stuck_count: 0
##     priority: "high"
##     needs_retesting: false
##     status_history:
##       - working: true
##         agent: "main"
##         comment: "Latest full integration run includes staff dashboard, platform-role and plant-scope regression coverage; backend suite is green."
##
##   - task: "Staff actions: KYC, user management, fleet, inventory, production, quality, accounting, notifications"
##     implemented: true
##     working: true
##     file: "backend/routers/staff.py, backend/routers/notify.py, backend/tests/test_staff_actions.py"
##     stuck_count: 0
##     priority: "high"
##     needs_retesting: false
##     status_history:
##       - working: true
##         agent: "main"
##         comment: "Action/RBAC regression tests are included in the latest 154-pass integration run. KYC remains manual Authority review, not automatic DigiLocker."
##
##   - task: "Dispatcher workflow + owner insights"
##     implemented: true
##     working: true
##     file: "backend/routers/staff.py, backend/routers/owner.py, backend/tests/test_iteration9_dispatch_rbac_insights.py"
##     stuck_count: 0
##     priority: "high"
##     needs_retesting: false
##     status_history:
##       - working: true
##         agent: "main"
##         comment: "Dispatcher assign/challan/dispatch RBAC and owner weekly insights tests are included in the latest green backend suite."
##
##   - task: "Driver trip, GPS API, POD and object authorization"
##     implemented: true
##     working: true
##     file: "backend/routers/driver.py, backend/routers/storage.py, backend/tests/test_driver_pod.py"
##     stuck_count: 0
##     priority: "high"
##     needs_retesting: false
##     status_history:
##       - working: true
##         agent: "main"
##         comment: "Backend lifecycle/POD/storage authorization scenarios pass in CI. Physical-device GPS behavior remains an external device test, not a backend failure."

## frontend:
##   - task: "Expo application compile/config quality gates"
##     implemented: true
##     working: true
##     file: "frontend/"
##     stuck_count: 0
##     priority: "high"
##     needs_retesting: false
##     status_history:
##       - working: true
##         agent: "main"
##         comment: "TypeScript, lint, Expo Doctor, public config validation and web preview build all pass on the hardening branch."
##
##   - task: "Android native generation and compile"
##     implemented: true
##     working: true
##     file: "frontend/app.json, frontend/"
##     stuck_count: 0
##     priority: "high"
##     needs_retesting: false
##     status_history:
##       - working: true
##         agent: "main"
##         comment: "Expo Android prebuild succeeded; generated applicationId com.trackmyrmc.concreteking and versionCode 61 were verified; Gradle :app:assembleDebug succeeded."
##
##   - task: "Role dashboards and end-to-end visual/runtime preview"
##     implemented: true
##     working: true
##     file: "frontend/app/, frontend/src/screens/"
##     stuck_count: 0
##     priority: "high"
##     needs_retesting: false
##     status_history:
##       - working: "NA"
##         agent: "main"
##         comment: "Compile/build gates are green. Final runtime visual review intentionally waits for a freshly deployed FastAPI preview backend and a connected preview build."
##       - working: true
##         agent: "testing"
##         comment: "PREVIEW CONNECTIVITY SMOKE TEST PASSED (5/5 checks). 1) App renders UI: Login screen loaded correctly with hero image, branding, input fields, and buttons. 2) Initial screen verified with screenshot. 3) OTP login flow with +919000000001: request-otp returned 200 with dev_otp=354342 (displayed on screen and auto-filled), verify-otp returned 200 with access_token. 4) Frontend->Backend connectivity confirmed: All API calls successful (POST /api/auth/request-otp → 200, POST /api/auth/verify-otp → 200, GET /api/me → 200, GET /api/customer/home → 200). 5) Successfully landed on authenticated customer dashboard at /customer showing 'Welcome back Rajesh Kumar', KYC verified status, active delivery (RMC-1001), nearby plants, and recent orders. Dev mode working correctly (no real SMS sent). Only 2 console warnings (React Native Web deprecation warnings), zero errors. Preview deployment fully functional."
##
##   - task: "Android background GPS on physical device"
##     implemented: true
##     working: "NA"
##     file: "frontend/src/location/tripTracking.ts, frontend/app.json"
##     stuck_count: 0
##     priority: "high"
##     needs_retesting: true
##     status_history:
##       - working: "NA"
##         agent: "main"
##         comment: "Native compile passes, but minimized/locked-screen background tracking requires a real Android device and cannot be certified by CI."

## metadata:
##   created_by: "main_agent"
##   version: "2.0"
##   test_sequence: 59
##   run_ui: false

## test_plan:
##   current_focus: []
##   stuck_tasks: []
##   test_all: false
##   test_priority: "high_first"

## agent_communication:
##   - agent: "main"
##     message: "Repository-controlled backend/frontend/native build gates are green. Do not claim runtime preview or background GPS complete until the isolated preview backend is deployed and device testing is performed."
##   - agent: "main"
##     message: "PREVIEW-ONLY boot: created git-ignored backend/.env (APP_ENV=development, MONGO_URL=mongodb://localhost:27017, DB_NAME=trackmyrmc, disposable dev JWT_SECRET/OTP_PEPPER, DEBUG_OTP=true, STORAGE_MODE=local). SMS/email providers intentionally UNCONFIGURED (no real messages). Please verify (do NOT change code): 1) GET /api/health returns 200 healthy; 2) Mongo reachable; 3) passwordless dev OTP login works using seeded accounts (e.g. +919000000001 customer, owner@trackmyrmc.test) where request-otp returns dev_otp and verify-otp issues a JWT. No production secrets are present."
##   - agent: "testing"
##     message: "PREVIEW boot verification complete - ALL CHECKS PASSED. Backend is healthy and ready for isolated preview deployment. Health endpoint, MongoDB connectivity, and dev OTP login flows (both SMS and email identifiers) all working correctly. No real SMS/email attempted (delivery.configured=false). Rate limiting functional. All 13 seeded accounts available for testing. No modifications made to code, .env, or dependencies as instructed."
##   - agent: "testing"
##     message: "PREVIEW CONNECTIVITY SMOKE TEST COMPLETE - ALL 5 CHECKS PASSED. Frontend Expo React Native Web app successfully: (a) renders UI with login screen, (b) connects to preview backend (all /api/* calls returning 200), (c) completes passwordless OTP login flow end-to-end with +919000000001, landing on authenticated customer dashboard showing Rajesh Kumar's profile, active delivery, and seeded data. Dev OTP mode working correctly (dev_otp=354342 displayed and auto-filled). Zero console errors, only 2 deprecation warnings. Preview deployment is fully functional and ready for user testing. Android background GPS remains untested (requires physical device)."

