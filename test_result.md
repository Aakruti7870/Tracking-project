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
##     working: "NA"
##     file: "frontend/app/, frontend/src/screens/"
##     stuck_count: 0
##     priority: "high"
##     needs_retesting: true
##     status_history:
##       - working: "NA"
##         agent: "main"
##         comment: "Compile/build gates are green. Final runtime visual review intentionally waits for a freshly deployed FastAPI preview backend and a connected preview build."
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
##   test_sequence: 57
##   run_ui: false

## test_plan:
##   current_focus:
##     - "Deploy isolated FastAPI/Mongo preview backend from fix/production-readiness-final"
##     - "Set verified PREVIEW_BACKEND_URL and build connected preview APK"
##     - "Run role-by-role visual/runtime preview and physical Android GPS check"
##   stuck_tasks: []
##   test_all: false
##   test_priority: "high_first"

## agent_communication:
##   - agent: "main"
##     message: "Repository-controlled backend/frontend/native build gates are green. Do not claim runtime preview or background GPS complete until the isolated preview backend is deployed and device testing is performed."
