from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class AdminUserDialogRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / 'admin.html').read_text(encoding='utf-8')
        cls.js = (ROOT / 'admin.js').read_text(encoding='utf-8')

    def test_dialog_controls_are_buttons_with_matching_ids(self):
        self.assertRegex(
            self.html,
            r'<button id="closeAdminUserDialog" class="dialog-close" type="button" aria-label="Close">×</button>',
        )
        self.assertRegex(
            self.html,
            r'<button class="admin-button" id="cancelAdminUserEdit" type="button">Cancel</button>',
        )

    def test_admin_bundle_url_changes_to_invalidate_previous_browser_cache(self):
        self.assertIn('admin.js?v=crm-20261125-3', self.html)

    def test_close_handler_is_delegated_after_dom_ready_before_dashboard_init(self):
        ready_listener = self.js.index("document.addEventListener('DOMContentLoaded'")
        dashboard_init = self.js.index('initDashboard();', ready_listener)
        setup = self.js[ready_listener:dashboard_init]
        self.assertIn("document.addEventListener('click'", setup)
        self.assertIn("target.closest('#closeAdminUserDialog, #cancelAdminUserEdit')", setup)
        self.assertIn('}, true);', setup)

    def test_admin_writes_still_check_the_loaded_primary_role(self):
        self.assertGreaterEqual(self.js.count("if (!state.isPrimary) return;"), 2)

    def test_cancel_resets_unsaved_values_and_only_closes_dialog(self):
        close_action = re.search(
            r'function closeAdminUserEditor\(\) \{(?P<body>.*?)\n\s*\}',
            self.js,
            re.S,
        )
        self.assertIsNotNone(close_action)
        self.assertIn("byId('editAdminUserForm')?.reset()", close_action['body'])
        self.assertIn("byId('adminUserDialog')?.close()", close_action['body'])
        self.assertNotIn('api(', close_action['body'])


if __name__ == '__main__':
    unittest.main()
