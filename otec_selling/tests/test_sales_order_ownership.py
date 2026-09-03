from unittest import TestCase

from otec_selling.sales_order_ownership import _requires_team_scope, _unique


class TestSalesOrderOwnershipHelpers(TestCase):
	def test_unique_ignores_blanks_and_duplicates(self):
		self.assertEqual(_unique([None, "", "sales@example.com", "sales@example.com"]), ["sales@example.com"])

	def test_multi_team_managers_do_not_require_a_default_team(self):
		self.assertFalse(_requires_team_scope("Team Leader"))
		self.assertFalse(_requires_team_scope("Supervisor"))
		self.assertTrue(_requires_team_scope("Sales Representative"))
