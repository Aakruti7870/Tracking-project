#!/usr/bin/env python3
"""
TrackMyRMC Customer KYC Verification Test Suite (Correction 1)
Tests KYC gating, verified-name profile contract, and cross-user safety
"""

import requests
import json
from typing import Dict, Any, Optional

# Backend URL - use preview host with /api prefix
BASE_URL = "https://93213563-b3b7-4701-a95c-7d81bd3cbaea.preview.emergentagent.com/api"

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

def print_test(name: str):
    print(f"\n{Colors.BLUE}{'='*80}{Colors.END}")
    print(f"{Colors.BLUE}TEST: {name}{Colors.END}")
    print(f"{Colors.BLUE}{'='*80}{Colors.END}")

def print_pass(message: str):
    print(f"{Colors.GREEN}✓ PASS: {message}{Colors.END}")

def print_fail(message: str):
    print(f"{Colors.RED}✗ FAIL: {message}{Colors.END}")

def print_info(message: str):
    print(f"{Colors.YELLOW}ℹ INFO: {message}{Colors.END}")

def get_customer_token(identifier: str) -> Optional[str]:
    """Helper: Get access token for a customer via dev OTP flow"""
    try:
        # Request OTP
        response = requests.post(
            f"{BASE_URL}/auth/request-otp",
            json={"identifier": identifier},
            timeout=10
        )
        if response.status_code != 200:
            print_fail(f"Failed to request OTP for {identifier}: {response.status_code}")
            return None
        
        data = response.json()
        dev_otp = data.get("dev_otp")
        if not dev_otp:
            print_fail(f"No dev_otp in response for {identifier}")
            return None
        
        # Verify OTP
        response = requests.post(
            f"{BASE_URL}/auth/verify-otp",
            json={"identifier": identifier, "code": dev_otp},
            timeout=10
        )
        if response.status_code != 200:
            print_fail(f"Failed to verify OTP for {identifier}: {response.status_code}")
            return None
        
        data = response.json()
        access_token = data.get("access_token")
        if not access_token:
            print_fail(f"No access_token in response for {identifier}")
            return None
        
        return access_token
    except Exception as e:
        print_fail(f"Exception getting token for {identifier}: {str(e)}")
        return None

def test_seeded_customer_kyc_verified():
    """Test 1: Seeded customer +919000000001 is KYC VERIFIED"""
    print_test("Seeded Customer KYC Status - GET /api/customer/kyc")
    
    identifier = "+919000000001"
    
    # Get token
    print_info(f"Getting token for {identifier}...")
    token = get_customer_token(identifier)
    if not token:
        print_fail("Failed to get customer token")
        return False
    
    print_pass(f"Token obtained for {identifier}")
    
    # Get KYC status
    print_info("Fetching KYC status...")
    try:
        response = requests.get(
            f"{BASE_URL}/customer/kyc",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        print_info(f"Status Code: {response.status_code}")
        print_info(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code != 200:
            print_fail(f"Expected status 200, got {response.status_code}")
            return False
        
        data = response.json()
        
        # Check status is VERIFIED
        if data.get("status") != "VERIFIED":
            print_fail(f"Expected status='VERIFIED', got '{data.get('status')}'")
            return False
        
        print_pass("Seeded customer KYC status is VERIFIED")
        return True
        
    except Exception as e:
        print_fail(f"KYC status check failed with exception: {str(e)}")
        return False

def test_me_endpoint_verified_customer():
    """Test 2: GET /api/me returns non-empty name and kyc_status=VERIFIED"""
    print_test("Verified Customer Profile - GET /api/me")
    
    identifier = "+919000000001"
    
    # Get token
    print_info(f"Getting token for {identifier}...")
    token = get_customer_token(identifier)
    if not token:
        print_fail("Failed to get customer token")
        return False
    
    # Get profile
    print_info("Fetching profile...")
    try:
        response = requests.get(
            f"{BASE_URL}/me",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        print_info(f"Status Code: {response.status_code}")
        print_info(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code != 200:
            print_fail(f"Expected status 200, got {response.status_code}")
            return False
        
        data = response.json()
        
        # Check name is non-empty
        name = data.get("name")
        if not name or not name.strip():
            print_fail(f"Expected non-empty name, got '{name}'")
            return False
        
        print_pass(f"Profile has non-empty name: '{name}'")
        
        # Check kyc_status is VERIFIED
        kyc_status = data.get("kyc_status")
        if kyc_status != "VERIFIED":
            print_fail(f"Expected kyc_status='VERIFIED', got '{kyc_status}'")
            return False
        
        print_pass("Profile has kyc_status='VERIFIED'")
        return True
        
    except Exception as e:
        print_fail(f"Profile check failed with exception: {str(e)}")
        return False

def test_home_endpoint_verified_customer():
    """Test 3: GET /api/customer/home returns kyc_status=VERIFIED and name"""
    print_test("Verified Customer Home - GET /api/customer/home")
    
    identifier = "+919000000001"
    
    # Get token
    print_info(f"Getting token for {identifier}...")
    token = get_customer_token(identifier)
    if not token:
        print_fail("Failed to get customer token")
        return False
    
    # Get home
    print_info("Fetching home...")
    try:
        response = requests.get(
            f"{BASE_URL}/customer/home",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        print_info(f"Status Code: {response.status_code}")
        print_info(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code != 200:
            print_fail(f"Expected status 200, got {response.status_code}")
            return False
        
        data = response.json()
        
        # Check name is present
        name = data.get("name")
        if not name or not name.strip():
            print_fail(f"Expected non-empty name, got '{name}'")
            return False
        
        print_pass(f"Home has non-empty name: '{name}'")
        
        # Check kyc_status is VERIFIED
        kyc_status = data.get("kyc_status")
        if kyc_status != "VERIFIED":
            print_fail(f"Expected kyc_status='VERIFIED', got '{kyc_status}'")
            return False
        
        print_pass("Home has kyc_status='VERIFIED'")
        return True
        
    except Exception as e:
        print_fail(f"Home check failed with exception: {str(e)}")
        return False

def test_place_order_verified_customer_draft():
    """Test 4: VERIFIED customer can POST /api/customer/orders with save_draft=true (NOT blocked by KYC)"""
    print_test("Place Order Gating (POSITIVE) - VERIFIED customer with save_draft=true")
    
    identifier = "+919000000001"
    
    # Get token
    print_info(f"Getting token for {identifier}...")
    token = get_customer_token(identifier)
    if not token:
        print_fail("Failed to get customer token")
        return False
    
    # Attempt to place draft order
    print_info("Attempting to place draft order...")
    
    # Minimal order payload with save_draft=true
    order_payload = {
        "plant_id": "000000000000000000000001",  # Dummy plant ID
        "grade": "M25",
        "quantity": 5.0,
        "site_name": "Test Site",
        "site_address": "123 Test Street, Test City",
        "delivery_date": "2026-12-31",
        "delivery_time": "10:00",
        "delivery_mode": "DELIVERY",
        "save_draft": True
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/customer/orders",
            headers={"Authorization": f"Bearer {token}"},
            json=order_payload,
            timeout=10
        )
        print_info(f"Status Code: {response.status_code}")
        print_info(f"Response: {response.text[:500]}")
        
        # Should NOT be 403 KYC_REQUIRED
        if response.status_code == 403:
            try:
                error_data = response.json()
                if "KYC_REQUIRED" in str(error_data):
                    print_fail("VERIFIED customer was blocked by KYC gating for draft order!")
                    return False
            except:
                pass
        
        # May fail for other reasons (invalid plant_id, validation, etc.) but NOT KYC
        if response.status_code == 403:
            print_fail(f"Got 403 Forbidden - should NOT be blocked by KYC for draft order")
            return False
        
        print_pass(f"Draft order NOT blocked by KYC (status: {response.status_code})")
        print_info(f"Note: Order may fail validation for other reasons (plant_id, etc.), but KYC did not block it")
        return True
        
    except Exception as e:
        print_fail(f"Place order test failed with exception: {str(e)}")
        return False

def test_place_order_not_verified_customer():
    """Test 5: NOT_STARTED customer gets 403 KYC_REQUIRED when posting non-draft order"""
    print_test("Place Order Gating (NEGATIVE) - NOT_STARTED customer with save_draft=false")
    
    # Register a fresh customer with a new phone number
    fresh_identifier = "+919999999999"
    
    print_info(f"Registering fresh customer {fresh_identifier}...")
    token = get_customer_token(fresh_identifier)
    if not token:
        print_fail("Failed to get token for fresh customer")
        return False
    
    print_pass(f"Fresh customer registered: {fresh_identifier}")
    
    # Verify KYC status is NOT_STARTED
    print_info("Verifying KYC status is NOT_STARTED...")
    try:
        response = requests.get(
            f"{BASE_URL}/customer/kyc",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            kyc_status = data.get("status")
            print_info(f"Fresh customer KYC status: {kyc_status}")
            if kyc_status != "NOT_STARTED":
                print_info(f"Note: Expected NOT_STARTED, got {kyc_status}")
    except Exception as e:
        print_info(f"Could not verify KYC status: {str(e)}")
    
    # Attempt to place non-draft order
    print_info("Attempting to place non-draft order (save_draft=false)...")
    
    order_payload = {
        "plant_id": "000000000000000000000001",
        "grade": "M25",
        "quantity": 5.0,
        "site_name": "Test Site",
        "site_address": "123 Test Street, Test City",
        "delivery_date": "2026-12-31",
        "delivery_time": "10:00",
        "delivery_mode": "DELIVERY",
        "save_draft": False  # Non-draft order
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/customer/orders",
            headers={"Authorization": f"Bearer {token}"},
            json=order_payload,
            timeout=10
        )
        print_info(f"Status Code: {response.status_code}")
        print_info(f"Response: {response.text[:500]}")
        
        # Should be 403 KYC_REQUIRED
        if response.status_code != 403:
            print_fail(f"Expected 403 Forbidden, got {response.status_code}")
            return False
        
        # Check for KYC_REQUIRED in response
        try:
            error_text = response.text
            if "KYC_REQUIRED" not in error_text:
                print_fail(f"Expected 'KYC_REQUIRED' in error response, got: {error_text}")
                return False
        except:
            print_fail("Could not parse error response")
            return False
        
        print_pass("NOT_STARTED customer correctly blocked with 403 KYC_REQUIRED")
        return True
        
    except Exception as e:
        print_fail(f"Place order test failed with exception: {str(e)}")
        return False

def test_fresh_customer_kyc_not_started():
    """Test 6: GET /api/customer/kyc for fresh customer returns NOT_STARTED"""
    print_test("Fresh Customer KYC Status - GET /api/customer/kyc")
    
    # Register a fresh customer
    fresh_identifier = "+919888888888"
    
    print_info(f"Registering fresh customer {fresh_identifier}...")
    token = get_customer_token(fresh_identifier)
    if not token:
        print_fail("Failed to get token for fresh customer")
        return False
    
    print_pass(f"Fresh customer registered: {fresh_identifier}")
    
    # Get KYC status
    print_info("Fetching KYC status...")
    try:
        response = requests.get(
            f"{BASE_URL}/customer/kyc",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        print_info(f"Status Code: {response.status_code}")
        print_info(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code != 200:
            print_fail(f"Expected status 200, got {response.status_code}")
            return False
        
        data = response.json()
        
        # Check status is NOT_STARTED
        if data.get("status") != "NOT_STARTED":
            print_fail(f"Expected status='NOT_STARTED', got '{data.get('status')}'")
            return False
        
        print_pass("Fresh customer KYC status is NOT_STARTED")
        return True
        
    except Exception as e:
        print_fail(f"KYC status check failed with exception: {str(e)}")
        return False

def test_kyc_start_unconfigured_provider():
    """Test 7: POST /api/customer/kyc/start returns controlled error (503) when provider unconfigured"""
    print_test("KYC Start with Unconfigured Provider - POST /api/customer/kyc/start")
    
    # Register a fresh customer
    fresh_identifier = "+919777777777"
    
    print_info(f"Registering fresh customer {fresh_identifier}...")
    token = get_customer_token(fresh_identifier)
    if not token:
        print_fail("Failed to get token for fresh customer")
        return False
    
    print_pass(f"Fresh customer registered: {fresh_identifier}")
    
    # Attempt to start KYC
    print_info("Attempting to start KYC (provider unconfigured)...")
    try:
        response = requests.post(
            f"{BASE_URL}/customer/kyc/start",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        print_info(f"Status Code: {response.status_code}")
        print_info(f"Response: {response.text[:500]}")
        
        # Should be 503 (Service Unavailable) for unconfigured provider
        if response.status_code == 503:
            print_pass("KYC start correctly returns 503 (DigiLocker not configured)")
            
            # Check error message mentions DigiLocker
            try:
                error_text = response.text.lower()
                if "digilocker" in error_text or "not configured" in error_text:
                    print_pass("Error message mentions DigiLocker/configuration")
            except:
                pass
            
            return True
        elif response.status_code == 500:
            print_fail("Got 500 Internal Server Error - should be controlled 503")
            return False
        elif response.status_code == 200:
            print_fail("Got 200 Success - should NOT succeed when provider unconfigured")
            return False
        else:
            print_fail(f"Expected 503, got {response.status_code}")
            return False
        
    except Exception as e:
        print_fail(f"KYC start test failed with exception: {str(e)}")
        return False

def test_cross_user_safety():
    """Test 8: Cross-user safety - customer token only reads/affects own KYC/profile"""
    print_test("Cross-User Safety - Customer can only access own KYC/profile")
    
    # Get tokens for two different customers
    customer1 = "+919000000001"  # Seeded VERIFIED customer
    customer2 = "+919666666666"  # Fresh customer
    
    print_info(f"Getting token for customer 1: {customer1}...")
    token1 = get_customer_token(customer1)
    if not token1:
        print_fail("Failed to get token for customer 1")
        return False
    
    print_info(f"Getting token for customer 2: {customer2}...")
    token2 = get_customer_token(customer2)
    if not token2:
        print_fail("Failed to get token for customer 2")
        return False
    
    print_pass("Got tokens for both customers")
    
    # Customer 1 should see VERIFIED status
    print_info("Customer 1 checking own KYC status...")
    try:
        response = requests.get(
            f"{BASE_URL}/customer/kyc",
            headers={"Authorization": f"Bearer {token1}"},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            status1 = data.get("status")
            print_info(f"Customer 1 KYC status: {status1}")
            if status1 != "VERIFIED":
                print_fail(f"Expected customer 1 to have VERIFIED status, got {status1}")
                return False
        else:
            print_fail(f"Customer 1 KYC check failed: {response.status_code}")
            return False
    except Exception as e:
        print_fail(f"Customer 1 KYC check failed: {str(e)}")
        return False
    
    # Customer 2 should see NOT_STARTED status
    print_info("Customer 2 checking own KYC status...")
    try:
        response = requests.get(
            f"{BASE_URL}/customer/kyc",
            headers={"Authorization": f"Bearer {token2}"},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            status2 = data.get("status")
            print_info(f"Customer 2 KYC status: {status2}")
            if status2 != "NOT_STARTED":
                print_fail(f"Expected customer 2 to have NOT_STARTED status, got {status2}")
                return False
        else:
            print_fail(f"Customer 2 KYC check failed: {response.status_code}")
            return False
    except Exception as e:
        print_fail(f"Customer 2 KYC check failed: {str(e)}")
        return False
    
    # Verify /api/me returns different profiles
    print_info("Verifying /api/me returns different profiles...")
    try:
        response1 = requests.get(
            f"{BASE_URL}/me",
            headers={"Authorization": f"Bearer {token1}"},
            timeout=10
        )
        response2 = requests.get(
            f"{BASE_URL}/me",
            headers={"Authorization": f"Bearer {token2}"},
            timeout=10
        )
        
        if response1.status_code == 200 and response2.status_code == 200:
            data1 = response1.json()
            data2 = response2.json()
            
            # Should have different user IDs or names
            if data1.get("id") == data2.get("id"):
                print_fail("Both customers have same user ID - cross-user leak!")
                return False
            
            print_pass("Customers have different profiles (different user IDs)")
        else:
            print_fail(f"Profile checks failed: {response1.status_code}, {response2.status_code}")
            return False
    except Exception as e:
        print_fail(f"Profile check failed: {str(e)}")
        return False
    
    print_pass("Cross-user safety verified - customers can only access own data")
    return True

def test_protected_routes_require_auth():
    """Test 9: Regression - protected routes require auth (401 without token)"""
    print_test("Regression - Protected Routes Require Auth")
    
    protected_routes = [
        "/customer/kyc",
        "/customer/home",
        "/customer/orders",
        "/me"
    ]
    
    all_passed = True
    
    for route in protected_routes:
        print_info(f"Testing {route} without auth...")
        try:
            response = requests.get(f"{BASE_URL}{route}", timeout=10)
            print_info(f"  Status Code: {response.status_code}")
            
            if response.status_code != 401:
                print_fail(f"  Expected 401 Unauthorized, got {response.status_code}")
                all_passed = False
            else:
                print_pass(f"  {route} correctly returns 401 without auth")
                
        except Exception as e:
            print_fail(f"  Request to {route} failed with exception: {str(e)}")
            all_passed = False
    
    if all_passed:
        print_pass("All protected routes correctly reject unauthenticated requests")
    else:
        print_fail("Some protected routes did not behave as expected")
    
    return all_passed

def test_owner_login_works():
    """Test 10: Regression - owner login still works"""
    print_test("Regression - Plant Owner Login")
    
    identifier = "owner@trackmyrmc.test"
    
    print_info(f"Testing owner login for {identifier}...")
    token = get_customer_token(identifier)
    
    if not token:
        print_fail("Owner login failed")
        return False
    
    print_pass(f"Owner login successful for {identifier}")
    
    # Verify role is plant_owner
    try:
        response = requests.get(
            f"{BASE_URL}/me",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            role = data.get("primary_role")
            if role == "plant_owner":
                print_pass(f"Owner has correct role: {role}")
                return True
            else:
                print_fail(f"Expected role='plant_owner', got '{role}'")
                return False
        else:
            print_fail(f"Owner profile check failed: {response.status_code}")
            return False
    except Exception as e:
        print_fail(f"Owner profile check failed: {str(e)}")
        return False

def main():
    """Run all KYC verification tests"""
    print(f"\n{Colors.BLUE}{'='*80}{Colors.END}")
    print(f"{Colors.BLUE}TrackMyRMC Customer KYC Verification Test Suite (Correction 1){Colors.END}")
    print(f"{Colors.BLUE}Testing backend at: {BASE_URL}{Colors.END}")
    print(f"{Colors.BLUE}{'='*80}{Colors.END}")
    
    results = {}
    
    # Test 1: Seeded customer KYC VERIFIED
    results["seeded_customer_kyc_verified"] = test_seeded_customer_kyc_verified()
    
    # Test 2: /api/me returns name and kyc_status=VERIFIED
    results["me_endpoint_verified_customer"] = test_me_endpoint_verified_customer()
    
    # Test 3: /api/customer/home returns kyc_status=VERIFIED and name
    results["home_endpoint_verified_customer"] = test_home_endpoint_verified_customer()
    
    # Test 4: VERIFIED customer can place draft order (NOT blocked by KYC)
    results["place_order_verified_customer_draft"] = test_place_order_verified_customer_draft()
    
    # Test 5: NOT_STARTED customer gets 403 KYC_REQUIRED
    results["place_order_not_verified_customer"] = test_place_order_not_verified_customer()
    
    # Test 6: Fresh customer KYC status is NOT_STARTED
    results["fresh_customer_kyc_not_started"] = test_fresh_customer_kyc_not_started()
    
    # Test 7: KYC start with unconfigured provider returns 503
    results["kyc_start_unconfigured_provider"] = test_kyc_start_unconfigured_provider()
    
    # Test 8: Cross-user safety
    results["cross_user_safety"] = test_cross_user_safety()
    
    # Test 9: Protected routes require auth
    results["protected_routes_require_auth"] = test_protected_routes_require_auth()
    
    # Test 10: Owner login works
    results["owner_login_works"] = test_owner_login_works()
    
    # Summary
    print(f"\n{Colors.BLUE}{'='*80}{Colors.END}")
    print(f"{Colors.BLUE}TEST SUMMARY{Colors.END}")
    print(f"{Colors.BLUE}{'='*80}{Colors.END}")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = f"{Colors.GREEN}PASS{Colors.END}" if result else f"{Colors.RED}FAIL{Colors.END}"
        print(f"{test_name}: {status}")
    
    print(f"\n{Colors.BLUE}Total: {passed}/{total} tests passed{Colors.END}")
    
    if passed == total:
        print(f"{Colors.GREEN}{'='*80}{Colors.END}")
        print(f"{Colors.GREEN}ALL TESTS PASSED ✓{Colors.END}")
        print(f"{Colors.GREEN}{'='*80}{Colors.END}")
        return 0
    else:
        print(f"{Colors.RED}{'='*80}{Colors.END}")
        print(f"{Colors.RED}SOME TESTS FAILED ✗{Colors.END}")
        print(f"{Colors.RED}{'='*80}{Colors.END}")
        return 1

if __name__ == "__main__":
    exit(main())
