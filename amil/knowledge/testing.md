# Odoo 17.0/18.0/19.0 Testing Rules

> Category: Testing | Target: Odoo 17.0/18.0/19.0 | Load with: MASTER.md + testing.md

## Test Base Classes

### Use `TransactionCase` for standard unit tests

**WRONG:**
```python
from odoo.tests.common import SavepointCase

class TestMyModel(SavepointCase):
    pass
```

**CORRECT:**
```python
from odoo.tests.common import TransactionCase

class TestMyModel(TransactionCase):
    pass
```

**Why:** `SavepointCase` is deprecated in Odoo 17.0. `TransactionCase` rolls back after each test method, providing proper isolation. Use `TransactionCase` for all non-HTTP tests.

### Use `HttpCase` for controller and UI tests

**WRONG:**
```python
from odoo.tests.common import TransactionCase

class TestMyController(TransactionCase):
    def test_route(self):
        self.url_open("/my/route")  # Not available on TransactionCase
```

**CORRECT:**
```python
from odoo.tests.common import HttpCase

class TestMyController(HttpCase):
    def test_route(self):
        response = self.url_open("/my/route")
        self.assertEqual(response.status_code, 200)
```

**Why:** `HttpCase` provides `url_open()`, `browser_js()`, and a running HTTP server. Only use it when testing HTTP endpoints or browser interactions -- it is slower than `TransactionCase`.

---

## setUpClass Pattern

### Use `@classmethod` and `super().setUpClass()` for shared test data

**WRONG:**
```python
class TestLibraryBook(TransactionCase):
    def setUp(self):
        super().setUp()
        self.book = self.env["library.book"].create({"name": "Test"})
```

**CORRECT:**
```python
class TestLibraryBook(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Book = cls.env["library.book"]
        cls.partner = cls.env["res.partner"].create({"name": "Test Publisher"})
        cls.book = cls.Book.create({
            "name": "Test Book",
            "isbn": "1234567890",
            "publisher_id": cls.partner.id,
        })
```

**Why:** `setUpClass` runs once per test class (not per test method), making tests faster. Use `cls` (not `self`) to assign shared records. Always call `super().setUpClass()` first.

### Assign the model reference to a class attribute

**WRONG:**
```python
def test_create(self):
    book = self.env["library.book"].create({"name": "New"})
```

**CORRECT:**
```python
@classmethod
def setUpClass(cls):
    super().setUpClass()
    cls.Book = cls.env["library.book"]

def test_create(self):
    book = self.Book.create({"name": "New"})
```

**Why:** Assigning the model to `cls.Book` avoids repeating `self.env["library.book"]` in every test method. Cleaner and consistent.

---

## CRUD Tests

### Test create with valid data and verify default field values

**WRONG:**
```python
def test_create(self):
    book = self.Book.create({"name": "Test"})
    # No assertions
```

**CORRECT:**
```python
def test_create_book(self):
    book = self.Book.create({
        "name": "Test Book",
        "isbn": "1234567890",
        "publisher_id": self.partner.id,
    })
    self.assertEqual(book.name, "Test Book")
    self.assertEqual(book.state, "draft")  # Verify default
    self.assertTrue(book.active)  # Verify default
```

**Why:** Always assert both the set values and expected defaults. A test without assertions proves nothing.

### Test write and verify changed values

**CORRECT:**
```python
def test_write_book(self):
    self.book.write({"name": "Updated Title"})
    self.assertEqual(self.book.name, "Updated Title")
```

### Test unlink and verify record is removed

**CORRECT:**
```python
def test_unlink_book(self):
    book_id = self.book.id
    self.book.unlink()
    result = self.Book.search([("id", "=", book_id)])
    self.assertFalse(result)
```

---

## Computed Field Tests

### Set dependency fields, then assert computed value

**WRONG:**
```python
def test_computed(self):
    self.book.is_long_book = True  # Setting computed field directly
    self.assertTrue(self.book.is_long_book)
```

**CORRECT:**
```python
def test_computed_is_long_book(self):
    book = self.Book.create({
        "name": "Long Book",
        "page_count": 600,
    })
    self.assertTrue(book.is_long_book)

def test_computed_not_long_book(self):
    book = self.Book.create({
        "name": "Short Book",
        "page_count": 100,
    })
    self.assertFalse(book.is_long_book)
```

**Why:** Never set a computed field directly. Set the dependency fields and verify the computed result. Test both truthy and falsy outcomes.

---

## Constraint Tests

### Use `assertRaises(ValidationError)` with invalid data

**WRONG:**
```python
def test_constraint(self):
    try:
        self.Book.create({"name": "Bad", "isbn": "123"})
    except Exception:
        pass  # Swallowed -- test always passes
```

**CORRECT:**
```python
from odoo.exceptions import ValidationError

def test_isbn_constraint_invalid(self):
    with self.assertRaises(ValidationError):
        self.Book.create({
            "name": "Bad ISBN",
            "isbn": "123",  # Neither 10 nor 13 chars
        })

def test_isbn_constraint_valid(self):
    book = self.Book.create({
        "name": "Good ISBN",
        "isbn": "1234567890",  # 10 chars
    })
    self.assertTrue(book.isbn)
```

**Why:** `assertRaises` context manager verifies the exact exception type. Always test both the invalid case (raises) and the valid case (does not raise).

---

## Access Rights Tests

### Create a user with specific groups, test with `with_user()`

**WRONG:**
```python
def test_access(self):
    # Testing as admin -- admin bypasses all access rules
    book = self.Book.create({"name": "Test"})
    self.assertTrue(book)
```

**CORRECT:**
```python
@classmethod
def setUpClass(cls):
    super().setUpClass()
    cls.Book = cls.env["library.book"]
    cls.user_librarian = cls.env["res.users"].create({
        "name": "Librarian",
        "login": "librarian@test.com",
        "groups_id": [(6, 0, [
            cls.env.ref("library.group_library_user").id,
        ])],
    })
    cls.user_public = cls.env["res.users"].create({
        "name": "Public",
        "login": "public@test.com",
        "groups_id": [(6, 0, [
            cls.env.ref("base.group_public").id,
        ])],
    })

def test_librarian_can_create(self):
    book = self.Book.with_user(self.user_librarian).create({
        "name": "New Book",
    })
    self.assertTrue(book)

def test_public_cannot_create(self):
    from odoo.exceptions import AccessError
    with self.assertRaises(AccessError):
        self.Book.with_user(self.user_public).create({
            "name": "Forbidden Book",
        })
```

**Why:** Testing as admin (the default `self.env.user`) bypasses all access rules. Always test with a user that has the specific group you want to verify.

---

## Workflow Tests

### Test state transitions via action methods

**WRONG:**
```python
def test_workflow(self):
    self.book.state = "available"  # Direct assignment, skips business logic
```

**CORRECT:**
```python
def test_action_make_available(self):
    self.assertEqual(self.book.state, "draft")
    self.book.action_make_available()
    self.assertEqual(self.book.state, "available")

def test_action_borrow(self):
    self.book.action_make_available()
    borrower = self.env["res.partner"].create({"name": "Reader"})
    self.book.action_borrow(borrower.id)
    self.assertEqual(self.book.state, "borrowed")
    self.assertEqual(self.book.borrower_id, borrower)
```

**Why:** Always trigger state changes through the model's action methods. Direct state assignment bypasses validation, side effects, and business logic.

---

## Test File Organization

### One test file per model, import in `tests/__init__.py`

**WRONG:**
```
tests/
    test_all.py          # All tests in one file
```

**CORRECT:**
```
tests/
    __init__.py          # from . import test_library_book, test_library_member
    test_library_book.py
    test_library_member.py
```

**Why:** One test file per model keeps tests focused and maintainable. The `tests/__init__.py` must import all test modules, or Odoo will not discover them.

### Name test files with `test_` prefix matching the model

**WRONG:**
```
tests/
    library_tests.py
    book_test.py
```

**CORRECT:**
```
tests/
    test_library_book.py      # For library.book model
    test_library_member.py    # For library.member model
```

**Why:** Odoo's test runner discovers files matching `test_*.py`. The file name should mirror the model name for easy navigation.

---

## Changed in 17.0

| What Changed | Before (16.0) | Now (17.0) | Notes |
|-------------|---------------|------------|-------|
| `SavepointCase` | Primary test class for class-level setup | Deprecated, use `TransactionCase` | `TransactionCase` now supports `setUpClass` properly |
| Test tags | `@tagged('post_install', '-at_install')` common | Same syntax, unchanged | Use tags to control when tests run |
| `Form` test helper | Available for simulating form views | Still available via `odoo.tests.common.Form` | Useful for testing onchange triggers |

---

## Common Mistakes

### Testing as admin masks permission issues

Tests run as the admin user by default. Admin bypasses all ACLs and record rules. If you only test as admin, you will never catch access control bugs. Always create test users with specific groups and use `with_user()`.

### Not using setUpClass (slow tests)

Using `setUp()` (instance method) instead of `setUpClass()` (class method) creates test records before every single test method. For a class with 10 tests, that is 10x the setup time. Use `setUpClass` for shared data.

### Testing implementation, not behavior

Do not test that a private method was called or that a field was set internally. Test the observable behavior: after calling `action_borrow()`, assert the state is `"borrowed"` and the borrower is set. This makes tests resilient to refactoring.

### Forgetting to import test modules in `tests/__init__.py`

If `tests/__init__.py` does not import your test file, Odoo will silently skip it. Always verify your `__init__.py` includes all test modules.

---

## pylint-odoo Rules

| Rule | Description | Fix |
|------|-------------|-----|
| W8106 | Missing test file for model | Add `tests/test_{model_name}.py` for each model |

## Changed in 19.0

No breaking changes to the testing framework in 19.0. The test base classes (`TransactionCase`, `HttpCase`), `setUpClass` pattern, `Form` helper, and test tags remain the same. Test code should be updated to use 19.0 ORM patterns (e.g., `_compute_display_name()` instead of `name_get()`, `_read_group()` instead of `read_group()`).

---
*Odoo 17.0/18.0/19.0 Testing -- loaded by test generation agents*
