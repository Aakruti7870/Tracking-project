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
# Testing Data - Main Agent and testing sub agent both should log testing data below this section
#====================================================================================================
## FEATURE: 10 Staff Role Dashboards (2026-06)
## backend:
##   - task: "Staff role dashboards router /api/staff (home + collections)"
##     implemented: true
##     working: "NA"
##     file: "backend/routers/staff.py"
##     priority: "high"
##     needs_retesting: true
##     status_history:
##         -working: "NA"
##         -agent: "main"
##         -comment: "New DRY router serving role-aware /api/staff/home (KPIs) and /api/staff/collection/{kind} for 10 roles: admin, dispatcher, operator, supervisor, accountant, quality_engineer, fleet_manager, store_manager, authority, central_admin. Verified via curl for dispatcher/store/authority/central/accountant. Seeded 9 new staff accounts + materials collection."
## frontend:
##   - task: "Role dashboards (tab shells + generic StaffHome/StaffCollection/StaffMore)"
##     implemented: true
##     working: "NA"
##     file: "frontend/app/{role}/, frontend/src/screens/Staff*.tsx"
##     priority: "high"
##     needs_retesting: true
##     status_history:
##         -working: "NA"
##         -agent: "main"
##         -comment: "Each of 10 roles has a GlassTabBar tab shell routing to StaffHome (KPI grid + primary list preview) and StaffCollection tabs + StaffMore. index.tsx routes each role to its folder."

## FEATURE: Staff actionable modules + Notifications + Maps plumbing (2026-06)
## backend:
##   - task: "KYC review (Authority approve/reject), User mgmt (Central Admin suspend/activate), Fleet (add vehicle/set status), Inventory (adjust/add material), Quality (record test), Operator (production start/complete), Accountant (record payment)"
##     implemented: true
##     working: "NA"
##     file: "backend/routers/staff.py, backend/routers/notify.py, backend/routers/maps.py, backend/models.py, backend/seed.py"
##     priority: "high"
##     needs_retesting: true
##     status_history:
##         -working: "NA"
##         -agent: "main"
##         -comment: "Curl-verified: KYC approve->VERIFIED, add vehicle, operator production/start actions present, quality record PASS, central users suspend actions present. Seeded 2 PENDING KYC (driver, plant). Notifications feed + read/read-all. Maps proxy reads GOOGLE_MAPS_KEY (currently empty -> NOT_CONFIGURED, graceful)."
## frontend:
##   - task: "Backend-driven action buttons in StaffCollection (approve/reject/suspend/activate/set-status/stock-in-out/record-payment/record-test), create modals (material/vehicle), amount+reason modals, Quality test screen, Notifications screen + bell, New Order Google Places autocomplete (key-ready)"
##     implemented: true
##     working: "NA"
##     file: "frontend/src/screens/StaffCollection.tsx, frontend/src/screens/StaffHome.tsx, frontend/app/quality-test/[id].tsx, frontend/app/notifications.tsx, frontend/app/new-order.tsx"
##     priority: "high"
##     needs_retesting: true
##     status_history:
##         -working: "NA"
##         -agent: "main"
##         -comment: "Generic actions rendered from backend item.actions; input modals for amount/reason; create header button. Notifications bell in staff header. Places search on new-order gracefully hidden until GOOGLE_MAPS_KEY set."
