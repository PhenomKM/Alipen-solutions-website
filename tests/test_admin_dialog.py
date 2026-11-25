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

    def test_dialog_controls_are_bound_before_session_role_is_loaded(self):
        session_load = self.js.index("const session = await api('/session')")
        setup_before_session = self.js[:session_load]
        self.assertNotIn('if (state.isPrimary)', setup_before_session)
        for control_id in ('closeAdminUserDialog', 'cancelAdminUserEdit', 'editAdminUserForm'):
            with self.subTest(control_id=control_id):
                self.assertIn(f"bind('{control_id}'", setup_before_session)

    def test_admin_writes_still_check_the_loaded_primary_role(self):
        self.assertIn("if (!state.isPrimary) return;", self.js)

    def test_cancel_resets_unsaved_values_and_only_closes_dialog(self):
        close_action = re.search(
            r'const closeAdminUserDialog = \(\) => \{(?P<body>.*?)\n\s*\};',
            self.js,
            re.S,
        )
        self.assertIsNotNone(close_action)
        self.assertIn("byId('editAdminUserForm')?.reset()", close_action['body'])
        self.assertIn("byId('adminUserDialog')?.close()", close_action['body'])
        self.assertNotIn('api(', close_action['body'])
        self.assertIn(
            "bind('cancelAdminUserEdit', 'click', closeAdminUserDialog)", self.js
        )


if __name__ == '__main__':
    unittest.main()
