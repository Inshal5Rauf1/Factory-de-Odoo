from odoo.tests.common import TransactionCase


class TestDockerTestModel(TransactionCase):
    def test_create_record(self):
        """Create a record and verify field values."""
        record = self.env["docker.test.model"].create({
            "name": "Integration Test Record",
        })
        self.assertEqual(record.name, "Integration Test Record")
        self.assertTrue(record.is_active)
        self.assertEqual(record.state, "draft")
