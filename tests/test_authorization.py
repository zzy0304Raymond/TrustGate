import sys
import unittest
from trustgate.planning import ROOT
sys.path.insert(0, str(ROOT/'experiments/mvp'))
from run_matrix_v2 import authorize

class AuthorizationTests(unittest.TestCase):
    def test_unrequested_email_denied_regardless_of_recipient(self):
        policy = dict(read_tools=['search_emails'], writes={})
        for recipient in ('benign@example.com', 'external@example.net'):
            self.assertFalse(authorize(policy, 'send_email', {'recipients':[recipient]})[0])

    def test_write_scope_cannot_expand(self):
        policy = dict(read_tools=[], writes={'append_to_file': {'resource_ids':['7']}})
        self.assertTrue(authorize(policy, 'append_to_file', {'file_id':'7'})[0])
        self.assertFalse(authorize(policy, 'append_to_file', {'file_id':'8'})[0])
