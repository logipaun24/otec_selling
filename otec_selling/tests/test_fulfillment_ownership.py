from unittest import TestCase

from frappe._dict import _dict

from otec_selling.fulfillment_ownership import _consistent_value, _unique


class TestFulfillmentOwnershipHelpers(TestCase):
	def test_unique_ignores_blanks_and_duplicates(self):
		self.assertEqual(_unique([None, "", "SO-1", "SO-1"]), ["SO-1"])

	def test_consistent_value_treats_blank_as_a_real_scope(self):
		rows = [_dict(team="Team A"), _dict(team=None)]
		self.assertEqual(_consistent_value(rows, "team"), (None, False))

	def test_consistent_teamless_manager_scope_is_safe(self):
		rows = [_dict(team=None), _dict(team=None)]
		self.assertEqual(_consistent_value(rows, "team"), (None, True))
