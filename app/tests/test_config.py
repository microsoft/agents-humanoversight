# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.

import unittest
from unittest.mock import patch, Mock
import sys
import os
import importlib


class TestConfig(unittest.TestCase):
    """Test configuration loading and environment variables."""
    
    def setUp(self):
        """Prepare for test by clearing module from sys.modules."""
        # Ensure the module is freshly loaded for each test
        if 'human_oversight.config' in sys.modules:
            del sys.modules['human_oversight.config']
    
    def tearDown(self):
        """Clean up after each test by reloading the config module."""
        if 'human_oversight.config' in sys.modules:
            del sys.modules['human_oversight.config']
    
    @patch.dict('os.environ', {'HO_LOGIC_APP_URL': 'https://test-url.example.com'}, clear=True)
    def test_logic_app_url_from_env(self):
        """Test loading the Logic App URL from environment variable."""
        # Force reload with patched environment
        import human_oversight.config
        importlib.reload(human_oversight.config)
        
        self.assertEqual(human_oversight.config.HO_LOGIC_APP_URL, 'https://test-url.example.com')

if __name__ == '__main__':
    unittest.main()
