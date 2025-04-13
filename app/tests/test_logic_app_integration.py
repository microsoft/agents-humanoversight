# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.

import unittest
import os
import uuid
import time
import json
import logging
import datetime
import requests
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class LogicAppIntegrationTest(unittest.TestCase):
    """
    Integration test for Logic App Human Oversight flow.
    
    This test sends real requests to the Logic App endpoint configured
    in environment variables and verifies the approval flow.
    
    IMPORTANT: Before running these tests:
    1. Make sure you've deployed the Logic App using the Bicep template
    2. Set the HO_LOGIC_APP_URL environment variable
    3. Set APPROVER_EMAILS environment variable with at least one email
    4. Note that actual emails will be sent when running these tests
    5. Set RUN_INTEGRATION_TEST=true to enable these tests
    """

    @classmethod
    def setUpClass(cls):
        """Set up test environment once for all tests."""
        # Check if integration tests should run
        run_integration_tests = os.getenv('RUN_INTEGRATION_TEST', '').lower() == 'true'
        if not run_integration_tests:
            raise unittest.SkipTest(
                "Integration tests are disabled. Set RUN_INTEGRATION_TEST=true "
                "environment variable to enable these tests."
            )
            
        # Check if required environment variables are set
        cls.logic_app_url = os.getenv('HO_LOGIC_APP_URL')
        if not cls.logic_app_url:
            raise unittest.SkipTest(
                "HO_LOGIC_APP_URL environment variable not set. "
                "Set this variable to run integration tests."
            )
            
        approver_emails_str = os.getenv('APPROVER_EMAILS')
        if not approver_emails_str:
            raise unittest.SkipTest(
                "APPROVER_EMAILS environment variable not set. "
                "Set this variable with comma-separated emails to run integration tests."
            )
        cls.approver_emails = [email.strip() for email in approver_emails_str.split(',')]
        
        # Check if we can access the Logic App URL
        try:
            # Just a HEAD request to check connectivity without triggering the Logic App
            requests.head(cls.logic_app_url, timeout=5)
            logger.info(f"Successfully connected to Logic App URL: {cls.logic_app_url}")
        except requests.RequestException as e:
            raise unittest.SkipTest(
                f"Could not connect to Logic App URL: {e}"
            )
            
        logger.info("Integration test setup complete")

    def test_logic_app_sends_approval_email(self):
        """
        Test that the Logic App sends an approval email when triggered.
        
        This test sends a real request to the Logic App, which will trigger
        a real email to be sent to the approver(s). You will need to manually
        check your email to confirm receipt.
        
        Note: This test doesn't wait for approval or check the result.
        It just verifies that the Logic App accepts the request without errors.
        """
        # Generate a unique test ID (important for tracking in logs/emails)
        test_id = str(uuid.uuid4())
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Prepare the request payload
        payload = {
            "agentName": "IntegrationTestAgent",
            "actionDescription": f"Logic App Test [{timestamp}]",
            "parameters": {
                "testId": test_id,
                "timestamp": timestamp,
                "isTest": True
            },
            "approverEmails": self.approver_emails,
            "correlationId": test_id
        }
        
        logger.info(f"Sending test request to Logic App with ID: {test_id}")
        logger.info(f"Request payload: {json.dumps(payload, indent=2)}")
        
        try:
            # Send the request to the Logic App
            response = requests.post(
                self.logic_app_url,
                json=payload,
                timeout=30  # Give it a reasonable timeout
            )
            
            # Check if request was accepted
            response.raise_for_status()
            
            logger.info(f"Request accepted by Logic App. Status code: {response.status_code}")
            logger.info(f"Response: {response.text}")
            
            # Validate response format (without checking approval status)
            response_data = response.json()
            self.assertIn("correlationId", response_data)
            self.assertEqual(test_id, response_data["correlationId"])
            self.assertIn("status", response_data)
            
            # Log the important information for manual verification
            logger.info("✓ Test request successfully sent to Logic App")
            logger.info(f"✓ Please check approver email ({', '.join(self.approver_emails)}) for an approval request")
            logger.info(f"✓ The email subject should contain: Logic App Test [{timestamp}]")
            
        except requests.RequestException as e:
            logger.error(f"Error sending request to Logic App: {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response status code: {e.response.status_code}")
                logger.error(f"Response content: {e.response.text}")
            raise
            
    def test_logic_app_approval_flow(self):
        """
        Test the complete Logic App approval flow with manual interaction.
        
        This test sends a request to the Logic App and then waits for manual
        approval via email. The test will poll the Logic App periodically for
        up to 5 minutes, waiting for approval.
        
        IMPORTANT: When you run this test, you will need to:
        1. Check your email for the approval request
        2. Click "Approve" in the email
        3. The test will then verify that the approval was processed correctly
        
        NOTE: This test will fail if approval is not granted within 5 minutes.
        """
        # Skip this test if in CI environment - needs manual interaction
        if os.getenv('CI') == 'true':
            self.skipTest("Skipping manual approval test in CI environment")
            
        # Generate a unique test ID (important for tracking in logs/emails)
        test_id = str(uuid.uuid4())
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Prepare the request payload - use very clear description for manual test
        payload = {
            "agentName": "ManualApprovalTest",
            "actionDescription": f"PLEASE APPROVE THIS TEST [{timestamp}]",
            "parameters": {
                "testId": test_id,
                "timestamp": timestamp,
                "isTest": True,
                "message": "This is an integration test - please approve this request"
            },
            "approverEmails": self.approver_emails,
            "correlationId": test_id
        }
        
        logger.info(f"Sending manual approval test to Logic App with ID: {test_id}")
        logger.info(f"IMPORTANT: Please check your email ({', '.join(self.approver_emails)})")
        logger.info(f"            and APPROVE the request with subject containing: PLEASE APPROVE THIS TEST [{timestamp}]")
        
        try:
            # Send the request to the Logic App
            response = requests.post(
                self.logic_app_url,
                json=payload,
                timeout=30
            )
            
            # Check if request was accepted
            response.raise_for_status()
            
            logger.info(f"Request accepted by Logic App. Status code: {response.status_code}")
            initial_response = response.json()
            logger.info(f"Initial response: {json.dumps(initial_response, indent=2)}")
            
            # Now poll for up to 5 minutes waiting for approval
            logger.info("Waiting for manual approval (up to 5 minutes)...")
            logger.info("PLEASE CHECK YOUR EMAIL AND APPROVE THE REQUEST NOW")
            
            max_retries = 30  # 30 retries * 10 seconds = 5 minutes
            for i in range(max_retries):
                # Wait before each retry (except first time)
                if i > 0:
                    time.sleep(10)  # Wait 10 seconds between retries
                
                # Make the same request again to get current status
                response = requests.post(
                    self.logic_app_url,
                    json=payload,
                    timeout=30
                )
                
                if response.status_code != 200:
                    logger.warning(f"Got non-200 response code: {response.status_code}")
                    continue
                
                response_data = response.json()
                status = response_data.get("status")
                approver = response_data.get("approver")
                
                logger.info(f"Poll {i+1}/{max_retries}: Status = {status}, Approver = {approver}")
                
                # If we got a definitive status, we can break the loop
                if status == "Approved":
                    logger.info(f"✓ Request was APPROVED by {approver}")
                    self.assertEqual(status, "Approved")
                    self.assertIsNotNone(approver)
                    return
                elif status == "Rejected":
                    logger.info(f"✗ Request was REJECTED by {approver}")
                    self.fail(f"Test failed: Request was rejected by {approver}")
                
                # If it's still pending, continue looping
                logger.info(f"Still waiting for approval ({i+1}/{max_retries})...")
            
            # If we got here, the test timed out waiting for approval
            logger.error("Timed out waiting for approval")
            self.fail("Test failed: Timed out waiting for approval")
            
        except requests.RequestException as e:
            logger.error(f"Error in approval flow test: {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response status code: {e.response.status_code}")
                logger.error(f"Response content: {e.response.text}")
            raise


if __name__ == '__main__':
    unittest.main()
