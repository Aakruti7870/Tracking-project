# Security File Inventory

All 348 tracked files at assessment time are classified below. Generated/static does not mean trusted; secret and dangerous-API scans included every tracked file.

| File | Classification |
|---|---|
| `.dockerignore` | BUILD / CI |
| `.emergent/cron/applied.hash` | BUILD / CI |
| `.emergent/cron/dispatch_webhook.sh` | BUILD / CI |
| `.emergent/cron/watch_crons.sh` | BUILD / CI |
| `.emergent/cron/webhook-crons` | BUILD / CI |
| `.emergent/cron/webhook_crond.sh` | BUILD / CI |
| `.emergent/emergent.yml` | BUILD / CI |
| `.emergent/markers/.bootstrap-complete` | BUILD / CI |
| `.emergent/markers/.restore-complete` | BUILD / CI |
| `.github/workflows/android-api23-compatibility.yml` | BUILD / CI |
| `.github/workflows/auth-routing-regression.yml` | BUILD / CI |
| `.github/workflows/cloud-run-container.yml` | BUILD / CI |
| `.github/workflows/deploy-production-cloud-run.yml` | BUILD / CI |
| `.github/workflows/deploy-production-web.yml` | BUILD / CI |
| `.github/workflows/play-policy-readiness.yml` | BUILD / CI |
| `.github/workflows/pre-aab-candidate-validation.yml` | BUILD / CI |
| `.github/workflows/pre-aab-e2e.yml` | BUILD / CI |
| `.github/workflows/production-readiness.yml` | BUILD / CI |
| `.github/workflows/release-signed-aab.yml` | BUILD / CI |
| `.github/workflows/repo-hygiene-audit.yml` | BUILD / CI |
| `.github/workflows/tracking-project-full-gate.yml` | BUILD / CI |
| `.gitignore` | GENERATED / STATIC |
| `Dockerfile` | BUILD / CI |
| `README.md` | GENERATED / STATIC |
| `backend/audit.py` | APPLICATION LOGIC |
| `backend/billing_service.py` | APPLICATION LOGIC |
| `backend/business_access.py` | SECURITY CRITICAL |
| `backend/business_models.py` | APPLICATION LOGIC |
| `backend/config.py` | SECURITY CRITICAL |
| `backend/database.py` | SECURITY CRITICAL |
| `backend/delivery_service.py` | APPLICATION LOGIC |
| `backend/models.py` | SECURITY CRITICAL |
| `backend/notifications.py` | APPLICATION LOGIC |
| `backend/order_service.py` | APPLICATION LOGIC |
| `backend/play_review.py` | SECURITY CRITICAL |
| `backend/production_service.py` | APPLICATION LOGIC |
| `backend/push_notifications.py` | APPLICATION LOGIC |
| `backend/pytest.ini` | APPLICATION LOGIC |
| `backend/requirements-ci.txt` | BUILD / CI |
| `backend/requirements-runtime.txt` | BUILD / CI |
| `backend/requirements.txt` | BUILD / CI |
| `backend/roles.py` | SECURITY CRITICAL |
| `backend/routers/__init__.py` | SECURITY CRITICAL |
| `backend/routers/account_deletion.py` | SECURITY CRITICAL |
| `backend/routers/auth.py` | SECURITY CRITICAL |
| `backend/routers/business_ui.py` | SECURITY CRITICAL |
| `backend/routers/customer.py` | SECURITY CRITICAL |
| `backend/routers/driver.py` | SECURITY CRITICAL |
| `backend/routers/finance_ops.py` | SECURITY CRITICAL |
| `backend/routers/hr_master.py` | SECURITY CRITICAL |
| `backend/routers/kyc_recovery.py` | SECURITY CRITICAL |
| `backend/routers/loads.py` | SECURITY CRITICAL |
| `backend/routers/maps.py` | SECURITY CRITICAL |
| `backend/routers/master_data.py` | SECURITY CRITICAL |
| `backend/routers/me.py` | SECURITY CRITICAL |
| `backend/routers/notify.py` | SECURITY CRITICAL |
| `backend/routers/operator_ops.py` | SECURITY CRITICAL |
| `backend/routers/owner.py` | SECURITY CRITICAL |
| `backend/routers/payroll_closure.py` | SECURITY CRITICAL |
| `backend/routers/payroll_concurrency_hotfix.py` | SECURITY CRITICAL |
| `backend/routers/payroll_guard.py` | SECURITY CRITICAL |
| `backend/routers/permanent_access.py` | SECURITY CRITICAL |
| `backend/routers/plant_discovery.py` | SECURITY CRITICAL |
| `backend/routers/plant_onboarding.py` | SECURITY CRITICAL |
| `backend/routers/plant_plans.py` | SECURITY CRITICAL |
| `backend/routers/play_review.py` | SECURITY CRITICAL |
| `backend/routers/public_policy.py` | SECURITY CRITICAL |
| `backend/routers/staff.py` | SECURITY CRITICAL |
| `backend/routers/staff_auth.py` | SECURITY CRITICAL |
| `backend/routers/staff_mfa.py` | SECURITY CRITICAL |
| `backend/routers/staff_passkeys.py` | SECURITY CRITICAL |
| `backend/routers/storage.py` | SECURITY CRITICAL |
| `backend/routers/workforce.py` | SECURITY CRITICAL |
| `backend/routers/workforce_reports.py` | SECURITY CRITICAL |
| `backend/routers/workforce_roster.py` | SECURITY CRITICAL |
| `backend/security.py` | SECURITY CRITICAL |
| `backend/seed.py` | APPLICATION LOGIC |
| `backend/seed_business.py` | APPLICATION LOGIC |
| `backend/server.py` | SECURITY CRITICAL |
| `backend/services/__init__.py` | APPLICATION LOGIC |
| `backend/services/digilocker.py` | APPLICATION LOGIC |
| `backend/tests/backend_test.py` | SECURITY RELEVANT |
| `backend/tests/conftest.py` | SECURITY RELEVANT |
| `backend/tests/test_account_deletion.py` | SECURITY RELEVANT |
| `backend/tests/test_business_domain_unit.py` | SECURITY RELEVANT |
| `backend/tests/test_customer_cube_follow_up_unit.py` | SECURITY RELEVANT |
| `backend/tests/test_customer_kyc_verify_unit.py` | SECURITY RELEVANT |
| `backend/tests/test_customer_plant_visibility.py` | SECURITY RELEVANT |
| `backend/tests/test_digilocker_unit.py` | SECURITY RELEVANT |
| `backend/tests/test_dispatch_workflow.py` | SECURITY RELEVANT |
| `backend/tests/test_driver_pod.py` | SECURITY RELEVANT |
| `backend/tests/test_hr_master_unit.py` | SECURITY RELEVANT |
| `backend/tests/test_iteration9_dispatch_rbac_insights.py` | SECURITY RELEVANT |
| `backend/tests/test_kyc_recovery_unit.py` | SECURITY RELEVANT |
| `backend/tests/test_maps_places_unit.py` | SECURITY RELEVANT |
| `backend/tests/test_multiload_delivery.py` | SECURITY RELEVANT |
| `backend/tests/test_order_lifecycle.py` | SECURITY RELEVANT |
| `backend/tests/test_payroll_closure_unit.py` | SECURITY RELEVANT |
| `backend/tests/test_permanent_access_unit.py` | SECURITY RELEVANT |
| `backend/tests/test_phase6_sos_prod_invoice_track.py` | SECURITY RELEVANT |
| `backend/tests/test_plant_owner_provisioning.py` | SECURITY RELEVANT |
| `backend/tests/test_plant_plans_unit.py` | SECURITY RELEVANT |
| `backend/tests/test_plant_staff_management.py` | SECURITY RELEVANT |
| `backend/tests/test_pre_aab_e2e.py` | SECURITY RELEVANT |
| `backend/tests/test_preview_authority_bootstrap.py` | SECURITY RELEVANT |
| `backend/tests/test_production_hardening_unit.py` | SECURITY RELEVANT |
| `backend/tests/test_push_notifications_unit.py` | SECURITY RELEVANT |
| `backend/tests/test_runtime_config_unit.py` | SECURITY RELEVANT |
| `backend/tests/test_split_login_auth_unit.py` | SECURITY RELEVANT |
| `backend/tests/test_staff_actions.py` | SECURITY RELEVANT |
| `backend/tests/test_staff_dashboards.py` | SECURITY RELEVANT |
| `backend/tests/test_staff_email_otp_onboarding_unit.py` | SECURITY RELEVANT |
| `backend/tests/test_staff_mfa_unit.py` | SECURITY RELEVANT |
| `backend/tests/test_staff_passkeys_security.py` | SECURITY RELEVANT |
| `backend/tests/test_workforce_reports_unit.py` | SECURITY RELEVANT |
| `backend/tests/test_workforce_roster_unit.py` | SECURITY RELEVANT |
| `backend/tests/test_workforce_unit.py` | SECURITY RELEVANT |
| `backend_kyc_test.py` | SECURITY RELEVANT |
| `backend_test.py` | SECURITY RELEVANT |
| `design_guidelines.json` | BUILD / CI |
| `docs/ARCHITECTURE_REFACTOR_PLAN.md` | GENERATED / STATIC |
| `docs/FRESH_PRODUCTION_CHECKLIST.md` | GENERATED / STATIC |
| `docs/FRESH_PRODUCTION_RELEASE.md` | GENERATED / STATIC |
| `docs/HERO_ASSET_MAPPING.md` | GENERATED / STATIC |
| `docs/HERO_CHANGELOG.md` | GENERATED / STATIC |
| `docs/HERO_PR_CHECKLIST.md` | GENERATED / STATIC |
| `docs/HERO_RENDERING_ACCEPTANCE.md` | GENERATED / STATIC |
| `docs/HERO_VISUAL_REFERENCE.md` | GENERATED / STATIC |
| `docs/PLANT_STAFF_MFA.md` | GENERATED / STATIC |
| `docs/PRODUCTION_DEPLOYMENT.md` | GENERATED / STATIC |
| `docs/frontend-simplification-audit.md` | GENERATED / STATIC |
| `frontend/.gitignore` | GENERATED / STATIC |
| `frontend/.npmrc` | GENERATED / STATIC |
| `frontend/Dockerfile` | BUILD / CI |
| `frontend/README.md` | GENERATED / STATIC |
| `frontend/app.config.js` | SECURITY RELEVANT |
| `frontend/app.json` | SECURITY RELEVANT |
| `frontend/app/+html.tsx` | UI ONLY |
| `frontend/app/_layout.tsx` | UI ONLY |
| `frontend/app/account-deletion-admin.tsx` | UI ONLY |
| `frontend/app/account-deletion-public.tsx` | UI ONLY |
| `frontend/app/account-deletion.tsx` | UI ONLY |
| `frontend/app/accountant/_layout.tsx` | UI ONLY |
| `frontend/app/accountant/billing.tsx` | UI ONLY |
| `frontend/app/accountant/index.tsx` | UI ONLY |
| `frontend/app/accountant/ledger.tsx` | UI ONLY |
| `frontend/app/accountant/more.tsx` | UI ONLY |
| `frontend/app/admin/_layout.tsx` | UI ONLY |
| `frontend/app/admin/fleet.tsx` | UI ONLY |
| `frontend/app/admin/index.tsx` | UI ONLY |
| `frontend/app/admin/more.tsx` | UI ONLY |
| `frontend/app/admin/orders.tsx` | UI ONLY |
| `frontend/app/authority/_layout.tsx` | UI ONLY |
| `frontend/app/authority/index.tsx` | UI ONLY |
| `frontend/app/authority/kyc.tsx` | UI ONLY |
| `frontend/app/authority/more.tsx` | UI ONLY |
| `frontend/app/authority/payment-control.tsx` | UI ONLY |
| `frontend/app/authority/plants.tsx` | UI ONLY |
| `frontend/app/business/[kind].tsx` | UI ONLY |
| `frontend/app/central_admin/_layout.tsx` | UI ONLY |
| `frontend/app/central_admin/index.tsx` | UI ONLY |
| `frontend/app/central_admin/more.tsx` | UI ONLY |
| `frontend/app/central_admin/plants.tsx` | UI ONLY |
| `frontend/app/central_admin/users.tsx` | UI ONLY |
| `frontend/app/challan/[id].tsx` | UI ONLY |
| `frontend/app/customer/_layout.tsx` | UI ONLY |
| `frontend/app/customer/compare-plants.tsx` | UI ONLY |
| `frontend/app/customer/cube-test-follow-up.tsx` | UI ONLY |
| `frontend/app/customer/documents.tsx` | UI ONLY |
| `frontend/app/customer/free-tools.tsx` | UI ONLY |
| `frontend/app/customer/index.tsx` | UI ONLY |
| `frontend/app/customer/more.tsx` | UI ONLY |
| `frontend/app/customer/orders.tsx` | UI ONLY |
| `frontend/app/customer/plants.tsx` | UI ONLY |
| `frontend/app/customer/pour-planner.tsx` | UI ONLY |
| `frontend/app/customer/projects.tsx` | UI ONLY |
| `frontend/app/customer/quotations.tsx` | UI ONLY |
| `frontend/app/customer/receiving-guide.tsx` | UI ONLY |
| `frontend/app/customer/sites.tsx` | UI ONLY |
| `frontend/app/dispatch-order/[id].tsx` | UI ONLY |
| `frontend/app/dispatcher/_layout.tsx` | UI ONLY |
| `frontend/app/dispatcher/dispatch.tsx` | UI ONLY |
| `frontend/app/dispatcher/fleet.tsx` | UI ONLY |
| `frontend/app/dispatcher/index.tsx` | UI ONLY |
| `frontend/app/dispatcher/more.tsx` | UI ONLY |
| `frontend/app/driver/_layout.tsx` | UI ONLY |
| `frontend/app/driver/attendance.tsx` | UI ONLY |
| `frontend/app/driver/index.tsx` | UI ONLY |
| `frontend/app/driver/more.tsx` | UI ONLY |
| `frontend/app/driver/trips.tsx` | UI ONLY |
| `frontend/app/employee-master.tsx` | UI ONLY |
| `frontend/app/fleet_manager/_layout.tsx` | UI ONLY |
| `frontend/app/fleet_manager/drivers.tsx` | UI ONLY |
| `frontend/app/fleet_manager/fleet.tsx` | UI ONLY |
| `frontend/app/fleet_manager/index.tsx` | UI ONLY |
| `frontend/app/fleet_manager/more.tsx` | UI ONLY |
| `frontend/app/index.tsx` | UI ONLY |
| `frontend/app/kyc.tsx` | UI ONLY |
| `frontend/app/kyc/return.tsx` | UI ONLY |
| `frontend/app/login.tsx` | UI ONLY |
| `frontend/app/mfa-setup.tsx` | UI ONLY |
| `frontend/app/my-payslip.tsx` | UI ONLY |
| `frontend/app/new-order.tsx` | UI ONLY |
| `frontend/app/notifications.tsx` | UI ONLY |
| `frontend/app/operator/_layout.tsx` | UI ONLY |
| `frontend/app/operator/index.tsx` | UI ONLY |
| `frontend/app/operator/more.tsx` | UI ONLY |
| `frontend/app/operator/production.tsx` | UI ONLY |
| `frontend/app/order/[id].tsx` | UI ONLY |
| `frontend/app/owner/_layout.tsx` | UI ONLY |
| `frontend/app/owner/billing-history.tsx` | UI ONLY |
| `frontend/app/owner/billing.tsx` | UI ONLY |
| `frontend/app/owner/incidents.tsx` | UI ONLY |
| `frontend/app/owner/index.tsx` | UI ONLY |
| `frontend/app/owner/more.tsx` | UI ONLY |
| `frontend/app/owner/operations.tsx` | UI ONLY |
| `frontend/app/owner/orders.tsx` | UI ONLY |
| `frontend/app/owner/quotation-requests.tsx` | UI ONLY |
| `frontend/app/passkey-ceremony.tsx` | UI ONLY |
| `frontend/app/passkey-setup.tsx` | UI ONLY |
| `frontend/app/payroll-closure.tsx` | UI ONLY |
| `frontend/app/plans-promotions.tsx` | UI ONLY |
| `frontend/app/plant-onboarding.tsx` | UI ONLY |
| `frontend/app/pod/[id].tsx` | UI ONLY |
| `frontend/app/privacy.tsx` | UI ONLY |
| `frontend/app/privacy_policy.tsx` | UI ONLY |
| `frontend/app/quality-test/[id].tsx` | UI ONLY |
| `frontend/app/quality_engineer/_layout.tsx` | UI ONLY |
| `frontend/app/quality_engineer/index.tsx` | UI ONLY |
| `frontend/app/quality_engineer/more.tsx` | UI ONLY |
| `frontend/app/quality_engineer/quality.tsx` | UI ONLY |
| `frontend/app/review-access.tsx` | UI ONLY |
| `frontend/app/role-home.tsx` | UI ONLY |
| `frontend/app/shift-roster.tsx` | UI ONLY |
| `frontend/app/sos.tsx` | UI ONLY |
| `frontend/app/store_manager/_layout.tsx` | UI ONLY |
| `frontend/app/store_manager/index.tsx` | UI ONLY |
| `frontend/app/store_manager/more.tsx` | UI ONLY |
| `frontend/app/store_manager/stock.tsx` | UI ONLY |
| `frontend/app/supervisor/_layout.tsx` | UI ONLY |
| `frontend/app/supervisor/incidents.tsx` | UI ONLY |
| `frontend/app/supervisor/index.tsx` | UI ONLY |
| `frontend/app/supervisor/more.tsx` | UI ONLY |
| `frontend/app/supervisor/operations.tsx` | UI ONLY |
| `frontend/app/support.tsx` | UI ONLY |
| `frontend/app/terms.tsx` | UI ONLY |
| `frontend/app/track/[id].tsx` | UI ONLY |
| `frontend/app/trip/[id].tsx` | UI ONLY |
| `frontend/app/workforce-reports.tsx` | UI ONLY |
| `frontend/app/workforce.tsx` | UI ONLY |
| `frontend/assets/fonts/Jakarta-Bold.ttf` | GENERATED / STATIC |
| `frontend/assets/fonts/Jakarta-Medium.ttf` | GENERATED / STATIC |
| `frontend/assets/fonts/Jakarta-Regular.ttf` | GENERATED / STATIC |
| `frontend/assets/fonts/Jakarta-SemiBold.ttf` | GENERATED / STATIC |
| `frontend/assets/fonts/Outfit-Bold.ttf` | GENERATED / STATIC |
| `frontend/assets/fonts/Outfit-SemiBold.ttf` | GENERATED / STATIC |
| `frontend/assets/fonts/SpaceMono-Regular.ttf` | GENERATED / STATIC |
| `frontend/assets/images/adaptive-icon.png` | GENERATED / STATIC |
| `frontend/assets/images/favicon.png` | GENERATED / STATIC |
| `frontend/assets/images/home-hero-dark.jpg` | GENERATED / STATIC |
| `frontend/assets/images/home-hero-light.jpg` | GENERATED / STATIC |
| `frontend/assets/images/icon.png` | GENERATED / STATIC |
| `frontend/assets/images/login-hero-dark.jpg` | GENERATED / STATIC |
| `frontend/assets/images/login-hero-light.jpg` | GENERATED / STATIC |
| `frontend/assets/images/play-store-icon.png` | GENERATED / STATIC |
| `frontend/assets/images/splash-image.png` | GENERATED / STATIC |
| `frontend/constants/testIds/auth.js` | GENERATED / STATIC |
| `frontend/constants/testIds/index.js` | GENERATED / STATIC |
| `frontend/eslint.config.js` | GENERATED / STATIC |
| `frontend/google-services.json` | SECURITY RELEVANT |
| `frontend/legacy-service-worker.js` | GENERATED / STATIC |
| `frontend/metro.config.js` | GENERATED / STATIC |
| `frontend/nginx.conf` | BUILD / CI |
| `frontend/package-lock.json` | BUILD / CI |
| `frontend/package.json` | BUILD / CI |
| `frontend/plugins/with-play-store-compatibility.js` | BUILD / CI |
| `frontend/scripts/check-fresh-production-release.mjs` | BUILD / CI |
| `frontend/scripts/check-play-policy-readiness.mjs` | BUILD / CI |
| `frontend/scripts/check-role-routing.mjs` | BUILD / CI |
| `frontend/scripts/cmd-guard.js` | BUILD / CI |
| `frontend/scripts/cmd-guard/matcher.js` | BUILD / CI |
| `frontend/scripts/cmd-guard/modes.js` | BUILD / CI |
| `frontend/scripts/cmd-guard/rules.js` | BUILD / CI |
| `frontend/scripts/cmd-guard/vendor/wildcard-match.js` | BUILD / CI |
| `frontend/scripts/install-guard.sh` | BUILD / CI |
| `frontend/scripts/reset-project.js` | BUILD / CI |
| `frontend/scripts/sync-shims.sh` | BUILD / CI |
| `frontend/src/__tests__/hero-rendering.guard.test.ts` | APPLICATION LOGIC |
| `frontend/src/api/client.ts` | SECURITY RELEVANT |
| `frontend/src/api/upload.ts` | SECURITY RELEVANT |
| `frontend/src/auth/AuthContext.tsx` | SECURITY RELEVANT |
| `frontend/src/auth/roleRoutes.ts` | SECURITY RELEVANT |
| `frontend/src/auth/webauthn.ts` | SECURITY RELEVANT |
| `frontend/src/components/GlassTabBar.tsx` | UI ONLY |
| `frontend/src/components/HomeHero.tsx` | UI ONLY |
| `frontend/src/components/KycBanner.tsx` | UI ONLY |
| `frontend/src/components/LiveMap.tsx` | UI ONLY |
| `frontend/src/components/LoadPlanner.tsx` | UI ONLY |
| `frontend/src/components/OrderCard.tsx` | UI ONLY |
| `frontend/src/components/OrderTimeline.tsx` | UI ONLY |
| `frontend/src/components/OwnerProductionBilling.tsx` | UI ONLY |
| `frontend/src/components/PlantCard.tsx` | UI ONLY |
| `frontend/src/components/PlantMap.tsx` | UI ONLY |
| `frontend/src/components/PlantMap.web.tsx` | UI ONLY |
| `frontend/src/components/QuickActionHub.tsx` | UI ONLY |
| `frontend/src/components/StateViews.tsx` | UI ONLY |
| `frontend/src/components/WeeklyInsights.tsx` | UI ONLY |
| `frontend/src/components/auth/OtpOrbitVerification.tsx` | UI ONLY |
| `frontend/src/components/ui/AppText.tsx` | UI ONLY |
| `frontend/src/components/ui/Badge.tsx` | UI ONLY |
| `frontend/src/components/ui/Button.tsx` | UI ONLY |
| `frontend/src/components/ui/Card.tsx` | UI ONLY |
| `frontend/src/components/ui/Input.tsx` | UI ONLY |
| `frontend/src/components/ui/MapPlaceholder.tsx` | UI ONLY |
| `frontend/src/components/ui/Skeleton.tsx` | UI ONLY |
| `frontend/src/components/ui/Toast.tsx` | UI ONLY |
| `frontend/src/constants/roles.ts` | APPLICATION LOGIC |
| `frontend/src/domain/order.ts` | APPLICATION LOGIC |
| `frontend/src/domain/plant.ts` | APPLICATION LOGIC |
| `frontend/src/hooks/use-icon-fonts.ts` | APPLICATION LOGIC |
| `frontend/src/hooks/useApi.ts` | APPLICATION LOGIC |
| `frontend/src/location/BackgroundLocationConsent.tsx` | APPLICATION LOGIC |
| `frontend/src/location/tripTracking.ts` | APPLICATION LOGIC |
| `frontend/src/maps/geo.ts` | APPLICATION LOGIC |
| `frontend/src/notifications/PushNotificationBridge.tsx` | APPLICATION LOGIC |
| `frontend/src/notifications/pushClient.ts` | APPLICATION LOGIC |
| `frontend/src/payments/cashfree.ts` | APPLICATION LOGIC |
| `frontend/src/payments/cashfree.web.ts` | APPLICATION LOGIC |
| `frontend/src/screens/BusinessModule.tsx` | UI ONLY |
| `frontend/src/screens/LoginScreen.tsx` | UI ONLY |
| `frontend/src/screens/StaffCollection.tsx` | UI ONLY |
| `frontend/src/screens/StaffHome.tsx` | UI ONLY |
| `frontend/src/screens/StaffMore.tsx` | UI ONLY |
| `frontend/src/screens/StaffTabs.tsx` | UI ONLY |
| `frontend/src/theme/ThemeProvider.tsx` | UI ONLY |
| `frontend/src/theme/tokens.ts` | UI ONLY |
| `frontend/src/utils/storage/index.ts` | SECURITY RELEVANT |
| `frontend/src/utils/storage/index.web.ts` | SECURITY RELEVANT |
| `frontend/src/utils/storage/storage-base.ts` | SECURITY RELEVANT |
| `frontend/tsconfig.json` | BUILD / CI |
| `memory/.gitkeep` | GENERATED / STATIC |
| `memory/PRD.md` | GENERATED / STATIC |
| `scripts/gen_mixer.py` | APPLICATION LOGIC |
| `scripts/repo_hygiene_audit.py` | APPLICATION LOGIC |
| `test_reports/.gitkeep` | GENERATED / STATIC |
| `test_reports/pytest/.gitkeep` | GENERATED / STATIC |
| `test_result.md` | GENERATED / STATIC |
| `tests/__init__.py` | GENERATED / STATIC |
