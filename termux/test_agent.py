import unittest
from unittest.mock import patch
import agent

class AgentSafetyTests(unittest.TestCase):
    def test_repo_safety(self):
        self.assertEqual(agent.safe_repo('owner/repo'), 'owner/repo')
        for invalid in ('', '../repo', 'owner/../repo', '/etc/passwd', 'owner/repo;rm -rf /'):
            with self.assertRaises(ValueError):
                agent.safe_repo(invalid)

    def test_id_validation(self):
        self.assertEqual(agent.validate_id('012345abcdef'), '012345abcdef')
        with self.assertRaises(ValueError):
            agent.validate_id('../danger')

    def test_prevent_secret_and_workflow_edits(self):
        for path in ('.env', '.env.local', '.github/workflows/ci.yml', 'secrets.pem', '../x', 'google-services.json'):
            self.assertFalse(agent.is_safe_file(path), path)
        self.assertTrue(agent.is_safe_file('mobile/App.js'))

    def test_redact_secrets(self):
        self.assertEqual(agent.redact('Bearer my-private-key', 'my-private-key'), 'Bearer [скрыто]')

    def test_cannot_execute_unknown_action(self):
        with self.assertRaises(ValueError):
            agent.validate_id('x' * 30)

if __name__ == '__main__':
    unittest.main()
