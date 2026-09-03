from unittest import TestCase

from otec_selling.sales_order_ownership import _unique


class TestSalesOrderOwnershipHelpers(TestCase):
	def test_unique_ignores_blanks_and_duplicates(self):
		self.assertEqual(_unique([None, "", "sales@example.com", "sales@example.com"]), ["sales@example.com"])
