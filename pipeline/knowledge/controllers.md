# Odoo 17.0/18.0/19.0 Controller Rules

> Category: Controllers | Target: Odoo 17.0/18.0/19.0 | Load with: MASTER.md + controllers.md

## Controller Class

### Inherit from `http.Controller`

**WRONG:**
```python
from odoo import http

class LibraryController:  # Missing inheritance
    pass
```

**CORRECT:**
```python
from odoo import http

class LibraryController(http.Controller):
    pass
```

**Why:** All Odoo controllers must inherit from `http.Controller`. Without it, routes are not registered and the controller is invisible to the HTTP dispatcher.

### Place controllers in the `controllers/` directory

**CORRECT:**
```
controllers/
    __init__.py      # from . import main
    main.py          # Controller class
```

**Why:** OCA convention places controllers in `controllers/`. The `__init__.py` must import the controller module, or Odoo will not discover it.

---

## Route Decorators

### Use `@http.route()` with required parameters

**WRONG:**
```python
@http.route("/library/books")  # Missing auth and type
def list_books(self):
    pass
```

**CORRECT:**
```python
@http.route(
    "/library/books",
    auth="user",
    type="http",
    methods=["GET"],
)
def list_books(self):
    books = http.request.env["library.book"].search([])
    return http.request.render("library.book_list_template", {
        "books": books,
    })
```

**Why:** Always specify `auth` (who can access) and `type` (HTTP or JSON-RPC). Without `auth`, the default is `"user"` but being explicit prevents confusion. Without `type`, default is `"http"`.

### Auth options

| Auth Value | Who Can Access | `request.env.user` |
|-----------|----------------|---------------------|
| `"user"` | Logged-in users only | The authenticated user |
| `"public"` | Anyone (logged-in or anonymous) | Public user if not logged in |
| `"none"` | No authentication check | No user context, no `request.env` |

**WRONG:**
```python
@http.route("/api/data", auth="none")
def get_data(self):
    records = http.request.env["my.model"].search([])  # FAILS: no env with auth="none"
```

**CORRECT:**
```python
@http.route("/api/data", auth="public")
def get_data(self):
    records = http.request.env["my.model"].sudo().search([])
    return http.request.make_json_response({"data": records.read(["name"])})
```

**Why:** `auth="none"` disables authentication entirely -- `request.env` is not available. Use `auth="public"` for unauthenticated access with a valid environment. Use `sudo()` when public users need to read data they do not have ACL access to.

### JSON-RPC endpoints use `type="json"`

**WRONG:**
```python
@http.route("/api/books", auth="user", type="http")
def api_books(self):
    import json
    data = json.loads(http.request.httprequest.data)  # Manual JSON parsing
```

**CORRECT:**
```python
@http.route("/api/books/list", auth="user", type="json")
def api_books(self, **kwargs):
    books = http.request.env["library.book"].search_read(
        [], fields=["name", "isbn", "state"]
    )
    return books  # Automatically serialized to JSON-RPC response
```

**Why:** `type="json"` automatically parses the JSON-RPC request body and serializes the return value. No manual `json.loads()` or `json.dumps()` needed. The client sends a JSON-RPC envelope; the response follows the JSON-RPC format.

---

## Request/Response

### Access the environment via `http.request.env`

**CORRECT:**
```python
@http.route("/library/book/<int:book_id>", auth="user", type="http")
def book_detail(self, book_id):
    book = http.request.env["library.book"].browse(book_id)
    if not book.exists():
        raise http.request.not_found()
    return http.request.render("library.book_detail_template", {
        "book": book,
    })
```

### Return HTML with `request.render()`

**CORRECT:**
```python
return http.request.render("library.book_list_template", {
    "books": books,
    "page_title": "All Books",
})
```

**Why:** `request.render()` renders a QWeb template and returns an HTML response. The first argument is the template XML ID. The second is the template context dictionary.

### Return JSON with `request.make_json_response()`

**CORRECT:**
```python
return http.request.make_json_response({
    "status": "success",
    "data": {"id": book.id, "name": book.name},
})
```

**Why:** `make_json_response()` creates a proper JSON HTTP response with correct Content-Type headers. Use this for REST-style endpoints with `type="http"`.

### Use `sudo()` carefully for public access

**WRONG:**
```python
@http.route("/public/books", auth="public")
def public_books(self):
    # Public user has no ACL for library.book -- crashes
    books = http.request.env["library.book"].search([])
```

**CORRECT:**
```python
@http.route("/public/books", auth="public")
def public_books(self):
    books = http.request.env["library.book"].sudo().search([
        ("state", "=", "available"),  # Only expose available books
    ])
    return http.request.render("library.public_book_list", {
        "books": books,
    })
```

**Why:** Public users typically have no ACL access. `sudo()` bypasses access rules. When using `sudo()`, always add domain filters to limit exposure -- never expose all records unconditionally.

---

## Website Controllers

### Use `website=True` for website-integrated pages

**CORRECT:**
```python
@http.route(
    "/library",
    auth="public",
    type="http",
    website=True,
)
def library_home(self):
    books = http.request.env["library.book"].sudo().search([
        ("state", "=", "available"),
    ])
    return http.request.render("library.website_home", {
        "books": books,
    })
```

**Why:** `website=True` enables website features: layout template wrapping, SEO, multi-website support, and the website editor. Only use it for pages that should appear within the website frontend.

### SEO-friendly URLs with slug

**CORRECT:**
```python
from odoo.addons.http_routing.models.ir_http import slug

@http.route("/library/book/<model('library.book'):book>", auth="public", website=True)
def book_page(self, book):
    return http.request.render("library.website_book_detail", {
        "book": book,
    })
```

**Why:** Using `<model('library.book'):book>` in the route pattern automatically resolves the slug (e.g., `/library/book/the-great-library-1`) to a recordset. This gives SEO-friendly URLs and handles 404s for missing records.

---

## Changed in 17.0

| What Changed | Before (16.0) | Now (17.0) | Notes |
|-------------|---------------|------------|-------|
| `make_json_response` | Available | Same, unchanged | Preferred for HTTP JSON responses |
| Route parameters | Same syntax | Same, unchanged | `<int:id>`, `<model():record>` |
| CSRF protection | Enabled by default | Same, enabled by default | Do not disable with `csrf=False` |
| `type="json"` | JSON-RPC format | Same, unchanged | Request/response follow JSON-RPC envelope |

---

## Common Mistakes

### Missing `auth` parameter

Without explicit `auth`, the default is `"user"`. This means anonymous users get a login redirect. If you intend public access, set `auth="public"` explicitly.

### Not handling CSRF

Odoo enables CSRF protection by default for `type="http"` POST routes. Do not set `csrf=False` unless you have a valid reason (e.g., external webhook). For forms, include the CSRF token:

```xml
<form method="POST" action="/library/submit">
    <input type="hidden" name="csrf_token" t-att-value="request.csrf_token()"/>
</form>
```

### Accessing `env` without `sudo()` for public routes

Public users have minimal permissions. If your public route reads model data, you almost certainly need `sudo()`. But always filter the domain to avoid exposing sensitive records.

### Returning raw strings instead of proper responses

**WRONG:**
```python
return "OK"  # No Content-Type, no status code
```

**CORRECT:**
```python
return http.request.make_response("OK", headers=[("Content-Type", "text/plain")])
```

## Changed in 19.0

| What Changed | Before (18.0) | Now (19.0) | Impact |
|-------------|---------------|------------|--------|
| `type="json"` | Valid route type for JSON-RPC | **Renamed** to `type="jsonrpc"` | **Breaking** -- `type="json"` causes error |
| Other route params | Same as 17.0/18.0 | Same, unchanged | No other breaking changes |

### `type="json"` renamed to `type="jsonrpc"`

**WRONG (causes error in 19.0):**
```python
@http.route("/api/books/list", auth="user", type="json")
def api_books(self, **kwargs):
    books = http.request.env["library.book"].search_read(
        [], fields=["name", "isbn", "state"]
    )
    return books
```

**CORRECT (19.0):**
```python
@http.route("/api/books/list", auth="user", type="jsonrpc")
def api_books(self, **kwargs):
    books = http.request.env["library.book"].search_read(
        [], fields=["name", "isbn", "state"]
    )
    return books
```

**Why:** Odoo 19 renamed the route type from `"json"` to `"jsonrpc"` for clarity, since the endpoint follows the JSON-RPC protocol (not plain JSON). The `type="http"` value is unchanged. All controllers using `type="json"` must be updated.

---
*Odoo 17.0/18.0/19.0 Controllers -- loaded by controller generation agents*
