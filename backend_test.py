import requests
import sys
import json
from datetime import datetime

class TelegramAutomationTester:
    def __init__(self, base_url="https://tg-scraper-ui.preview.emergentagent.com"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.account_id = None
        self.log_id = None

    def run_test(self, name, method, endpoint, expected_status, data=None, params=None):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {method} {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    response_data = response.json()
                    print(f"   Response: {json.dumps(response_data, indent=2)}")
                    return True, response_data
                except:
                    return True, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   Error: {json.dumps(error_data, indent=2)}")
                except:
                    print(f"   Error: {response.text}")
                return False, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_health_check(self):
        """Test health check endpoint"""
        success, response = self.run_test(
            "Health Check",
            "GET",
            "api/health",
            200
        )
        return success

    def test_request_code(self, phone_number="+5511999999999"):
        """Test request verification code"""
        success, response = self.run_test(
            "Request Verification Code",
            "POST",
            "api/accounts/request-code",
            200,
            data={"phone_number": phone_number}
        )
        if success and 'account_id' in response:
            self.account_id = response['account_id']
            print(f"   Account ID: {self.account_id}")
        return success

    def test_verify_code(self, phone_number="+5511999999999", code="12345"):
        """Test code verification"""
        success, response = self.run_test(
            "Verify Code",
            "POST",
            "api/accounts/verify-code",
            200,
            data={"phone_number": phone_number, "code": code}
        )
        return success

    def test_get_accounts(self):
        """Test get accounts"""
        success, response = self.run_test(
            "Get Accounts",
            "GET",
            "api/accounts",
            200
        )
        if success and isinstance(response, list) and len(response) > 0:
            # Store the first account ID for further tests
            if not self.account_id:
                self.account_id = response[0]['id']
                print(f"   Using Account ID: {self.account_id}")
        return success

    def test_activate_account(self):
        """Test activate account"""
        if not self.account_id:
            print("❌ No account ID available for activation test")
            return False
            
        success, response = self.run_test(
            "Activate Account",
            "POST",
            f"api/accounts/{self.account_id}/activate",
            200
        )
        return success

    def test_start_automation(self):
        """Test start automation"""
        if not self.account_id:
            print("❌ No account ID available for automation test")
            return False
            
        automation_data = {
            "account_id": self.account_id,
            "source_groups": ["@test_group1", "@test_group2"],
            "target_group": "@target_group",
            "delay_min": 6,
            "delay_max": 15,
            "max_members": 10
        }
        
        success, response = self.run_test(
            "Start Automation",
            "POST",
            "api/automation/start",
            200,
            data=automation_data
        )
        
        if success and 'log_id' in response:
            self.log_id = response['log_id']
            print(f"   Log ID: {self.log_id}")
        return success

    def test_get_automation_logs(self):
        """Test get automation logs"""
        success, response = self.run_test(
            "Get Automation Logs",
            "GET",
            "api/automation/logs",
            200
        )
        return success

    def test_get_automation_stats(self):
        """Test get automation stats"""
        success, response = self.run_test(
            "Get Automation Stats",
            "GET",
            "api/automation/stats",
            200
        )
        return success

    def test_stop_automation(self):
        """Test stop automation"""
        if not self.log_id:
            print("❌ No log ID available for stop automation test")
            return False
            
        success, response = self.run_test(
            "Stop Automation",
            "POST",
            f"api/automation/{self.log_id}/stop",
            200
        )
        return success

    def test_delete_account(self):
        """Test delete account"""
        if not self.account_id:
            print("❌ No account ID available for deletion test")
            return False
            
        success, response = self.run_test(
            "Delete Account",
            "DELETE",
            f"api/accounts/{self.account_id}",
            200
        )
        return success

def main():
    print("🚀 Starting Telegram Automation API Tests")
    print("=" * 50)
    
    tester = TelegramAutomationTester()
    
    # Test sequence
    test_results = []
    
    # Basic health check
    test_results.append(("Health Check", tester.test_health_check()))
    
    # Account management flow
    test_results.append(("Request Code", tester.test_request_code()))
    test_results.append(("Verify Code", tester.test_verify_code()))
    test_results.append(("Get Accounts", tester.test_get_accounts()))
    test_results.append(("Activate Account", tester.test_activate_account()))
    
    # Automation flow
    test_results.append(("Start Automation", tester.test_start_automation()))
    test_results.append(("Get Logs", tester.test_get_automation_logs()))
    test_results.append(("Get Stats", tester.test_get_automation_stats()))
    test_results.append(("Stop Automation", tester.test_stop_automation()))
    
    # Cleanup
    test_results.append(("Delete Account", tester.test_delete_account()))
    
    # Print summary
    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY")
    print("=" * 50)
    
    for test_name, result in test_results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print(f"\nTotal Tests: {tester.tests_run}")
    print(f"Passed: {tester.tests_passed}")
    print(f"Failed: {tester.tests_run - tester.tests_passed}")
    print(f"Success Rate: {(tester.tests_passed / tester.tests_run * 100):.1f}%")
    
    # Return exit code
    return 0 if tester.tests_passed == tester.tests_run else 1

if __name__ == "__main__":
    sys.exit(main())