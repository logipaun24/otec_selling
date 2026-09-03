from unittest import TestCase

from otec_selling.sales_order_ownership import _allows_multiple_team_scopes, _unique


class TestSalesOrderOwnershipHelpers(TestCase):
	def test_unique_ignores_blanks_and_duplicates(self):
		self.assertEqual(_unique([None, "", "sales@example.com", "sales@example.com"]), ["sales@example.com"])

	def test_only_managers_can_use_multiple_team_scopes(self):
		self.assertTrue(_allows_multiple_team_scopes("Team Leader"))
		self.assertTrue(_allows_multiple_team_scopes("Supervisor"))
		self.assertFalse(_allows_multiple_team_scopes("Sales Representative"))
