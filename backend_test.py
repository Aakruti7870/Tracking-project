#!/usr/bin/env python3
"""
TrackMyRMC Preview Boot Verification Test Suite
Tests backend health, MongoDB connectivity, and dev OTP login flow
"""

import requests
import json
from typing import Dict, Any

# Backend URL - internal testing at localhost:8001
BASE_URL = "http://localhost:8001"

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

def test_health_endpoint():
    """Test 1: Backend boot health - GET /api/health"""
    print_test("Backend Health Check - GET /api/health")
    
    try:
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        print_info(f"Status Code: {response.status_code}")
        print_info(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code != 200:
            print_fail(f"Expected status 200, got {response.status_code}")
            return False
        
        data = response.json()
        
        # Check for required fields
        if "status" not in data:
            print_fail("Response missing 'status' field")
            return False
        
        if data["status"] != "healthy":
            print_fail(f"Expected status='healthy', got '{data['status']}'")
            return False
        
        # Check notifications.configured = false
        if "notifications" in data and "configured" in data["notifications"]:
            if data["notifications"]["configured"] != False:
                print_fail(f"Expected notifications.configured=false, got {data['notifications']['configured']}")
                return False
            print_pass("notifications.configured=false (SMS/email unconfigured as expected)")
        else:
            print_info("notifications.configured field not present in response")
        
        print_pass("Health endpoint returns 200 with status='healthy'")
        return True
        
    except Exception as e:
        print_fail(f"Health check failed with exception: {str(e)}")
        return False

def test_root_endpoint():
    """Test 2: Root API endpoint - GET /api/"""
    print_test("Root API Endpoint - GET /api/")
    
    try:
        response = requests.get(f"{BASE_URL}/api/", timeout=10)
        print_info(f"Status Code: {response.status_code}")
        print_info(f"Response: {response.text[:500]}")
        
        if response.status_code != 200:
            print_fail(f"Expected status 200, got {response.status_code}")
            return False
        
        print_pass("Root endpoint returns 200")
        return True
        
    except Exception as e:
        print_fail(f"Root endpoint test failed with exception: {str(e)}")
        return False

def test_dev_otp_customer_login():
    """Test 3: Dev OTP login flow with Customer account (+919000000001)"""
    print_test("Dev OTP Login Flow - Customer (+919000000001)")
    
    identifier = "+919000000001"
    
    # Step 1: Request OTP
    print_info("Step 1: Requesting OTP...")
    try:
        response = requests.post(
            f"{BASE_URL}/api/auth/request-otp",
            json={"identifier": identifier},
            timeout=10
        )
        print_info(f"Status Code: {response.status_code}")
        print_info(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code != 200:
            print_fail(f"Request OTP failed with status {response.status_code}")
            return False
        
        data = response.json()
        
        # Check for OTP_SENT status
        if data.get("status") != "OTP_SENT":
            print_fail(f"Expected status='OTP_SENT', got '{data.get('status')}'")
            return False
        
        # Check for dev_otp in response
        if "dev_otp" not in data:
            print_fail("dev_otp not present in response (DEBUG_OTP should be true)")
            return False
        
        dev_otp = data["dev_otp"]
        print_pass(f"OTP requested successfully, dev_otp={dev_otp}")
        
        # Check delivery.configured = false
        if "delivery" in data and "configured" in data["delivery"]:
            if data["delivery"]["configured"] != False:
                print_fail(f"Expected delivery.configured=false, got {data['delivery']['configured']}")
                return False
            print_pass("delivery.configured=false (no real SMS sent)")
        
    except Exception as e:
        print_fail(f"Request OTP failed with exception: {str(e)}")
        return False
    
    # Step 2: Verify OTP
    print_info("Step 2: Verifying OTP...")
    try:
        response = requests.post(
            f"{BASE_URL}/api/auth/verify-otp",
            json={"identifier": identifier, "code": dev_otp},
            timeout=10
        )
        print_info(f"Status Code: {response.status_code}")
        print_info(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code != 200:
            print_fail(f"Verify OTP failed with status {response.status_code}")
            return False
        
        data = response.json()
        
        # Check for access_token
        if "access_token" not in data:
            print_fail("access_token not present in response")
            return False
        
        # Check role
        if data.get("role") != "customer":
            print_fail(f"Expected role='customer', got '{data.get('role')}'")
            return False
        
        # Check name
        if data.get("name") != "Rajesh Kumar":
            print_fail(f"Expected name='Rajesh Kumar', got '{data.get('name')}'")
            return False
        
        print_pass(f"OTP verified successfully, JWT issued for customer 'Rajesh Kumar'")
        return True
        
    except Exception as e:
        print_fail(f"Verify OTP failed with exception: {str(e)}")
        return False

def test_dev_otp_owner_login():
    """Test 4: Dev OTP login flow with Plant Owner account (owner@trackmyrmc.test)"""
    print_test("Dev OTP Login Flow - Plant Owner (owner@trackmyrmc.test)")
    
    identifier = "owner@trackmyrmc.test"
    
    # Step 1: Request OTP
    print_info("Step 1: Requesting OTP...")
    try:
        response = requests.post(
            f"{BASE_URL}/api/auth/request-otp",
            json={"identifier": identifier},
            timeout=10
        )
        print_info(f"Status Code: {response.status_code}")
        print_info(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code != 200:
            print_fail(f"Request OTP failed with status {response.status_code}")
            return False
        
        data = response.json()
        
        # Check for OTP_SENT status
        if data.get("status") != "OTP_SENT":
            print_fail(f"Expected status='OTP_SENT', got '{data.get('status')}'")
            return False
        
        # Check for dev_otp in response
        if "dev_otp" not in data:
            print_fail("dev_otp not present in response (DEBUG_OTP should be true)")
            return False
        
        dev_otp = data["dev_otp"]
        print_pass(f"OTP requested successfully, dev_otp={dev_otp}")
        
        # Check delivery.configured = false
        if "delivery" in data and "configured" in data["delivery"]:
            if data["delivery"]["configured"] != False:
                print_fail(f"Expected delivery.configured=false, got {data['delivery']['configured']}")
                return False
            print_pass("delivery.configured=false (no real email sent)")
        
    except Exception as e:
        print_fail(f"Request OTP failed with exception: {str(e)}")
        return False
    
    # Step 2: Verify OTP
    print_info("Step 2: Verifying OTP...")
    try:
        response = requests.post(
            f"{BASE_URL}/api/auth/verify-otp",
            json={"identifier": identifier, "code": dev_otp},
            timeout=10
        )
        print_info(f"Status Code: {response.status_code}")
        print_info(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code != 200:
            print_fail(f"Verify OTP failed with status {response.status_code}")
            return False
        
        data = response.json()
        
        # Check for access_token
        if "access_token" not in data:
            print_fail("access_token not present in response")
            return False
        
        # Check role
        if data.get("role") != "plant_owner":
            print_fail(f"Expected role='plant_owner', got '{data.get('role')}'")
            return False
        
        # Check name contains "Owner" or "Concrete King"
        name = data.get("name", "")
        if "Concrete King" not in name:
            print_info(f"Note: Expected name to contain 'Concrete King', got '{name}'")
        
        print_pass(f"OTP verified successfully, JWT issued for plant_owner '{name}'")
        return True
        
    except Exception as e:
        print_fail(f"Verify OTP failed with exception: {str(e)}")
        return False

def test_mongodb_connectivity():
    """Test 5: MongoDB connectivity (demonstrated by successful OTP insertion)"""
    print_test("MongoDB Connectivity")
    
    print_info("MongoDB connectivity is demonstrated by successful OTP request/verify operations")
    print_info("The OTP flow requires writing to MongoDB (inserting OTP document)")
    print_info("If the above OTP tests passed, MongoDB is connected and working")
    
    # We can also check if we can make a simple request that would fail if Mongo was down
    try:
        response = requests.post(
            f"{BASE_URL}/api/auth/request-otp",
            json={"identifier": "+919000000001"},
            timeout=10
        )
        
        if response.status_code == 200:
            print_pass("MongoDB connectivity confirmed (OTP document successfully inserted)")
            return True
        else:
            print_fail(f"MongoDB connectivity test failed with status {response.status_code}")
            return False
            
    except Exception as e:
        print_fail(f"MongoDB connectivity test failed with exception: {str(e)}")
        return False

def main():
    """Run all preview boot verification tests"""
    print(f"\n{Colors.BLUE}{'='*80}{Colors.END}")
    print(f"{Colors.BLUE}TrackMyRMC Preview Boot Verification Test Suite{Colors.END}")
    print(f"{Colors.BLUE}Testing backend at: {BASE_URL}{Colors.END}")
    print(f"{Colors.BLUE}{'='*80}{Colors.END}")
    
    results = {}
    
    # Test 1: Health endpoint
    results["health_endpoint"] = test_health_endpoint()
    
    # Test 2: Root endpoint
    results["root_endpoint"] = test_root_endpoint()
    
    # Test 3: MongoDB connectivity
    results["mongodb_connectivity"] = test_mongodb_connectivity()
    
    # Test 4: Customer OTP login
    results["customer_otp_login"] = test_dev_otp_customer_login()
    
    # Test 5: Owner OTP login
    results["owner_otp_login"] = test_dev_otp_owner_login()
    
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
