# Odoo 17.0/18.0/19.0 OWL 2 Component Rules

> Loaded alongside MASTER.md. Covers OWL 2 component authoring in Odoo 17+,
> including lifecycle hooks, reactive state, services, registry, event handling,
> props, effects, patching, and common widget patterns.

## OWL 2 in Odoo 17-19

Odoo 17.0 ships with **OWL 2** (Odoo Web Library), a reactive component framework
inspired by React and Vue. All custom JS widgets, fields, actions, and systray
items are OWL 2 components.

Key differences from OWL 1 (Odoo 16 and earlier):
- `setup()` replaces `constructor()` and `willStart()` for hook registration
- Lifecycle hooks (`onWillStart`, `onMounted`, `onWillUnmount`, etc.) are
  registered inside `setup()` via imported functions, not class methods
- `useState()` is the only way to create reactive state
- Services are injected via `useService()`, never imported directly
- Templates are referenced by static string, never inline

All JS must use the `/** @odoo-module */` header and ES module imports.

## Component Lifecycle

### Fetch data in the correct lifecycle hook

**WRONG:**
```javascript
import { Component } from "@odoo/owl";

export class MyWidget extends Component {
    setup() {
        // Fetching data in setup() -- setup is synchronous!
        this.data = await this.loadData();
    }
}
```

**CORRECT:**
```javascript
import { Component, onWillStart } from "@odoo/owl";

export class MyWidget extends Component {
    setup() {
        onWillStart(() => this.loadData());
    }

    async loadData() {
        this.data = await this.env.services.rpc("/my/endpoint");
    }
}
```

**Why:** `setup()` is synchronous and cannot use `await`. Asynchronous initialization must be registered via `onWillStart()`, which is called before the first render and can return a Promise. Placing `await` in `setup()` silently breaks the component lifecycle.

### Use `onMounted` / `onWillUnmount` for DOM work

**WRONG:**
```javascript
setup() {
    // Accessing DOM in setup -- DOM doesn't exist yet
    const el = document.querySelector(".my-widget");
    el.addEventListener("scroll", this.onScroll);
}
```

**CORRECT:**
```javascript
import { onMounted, onWillUnmount } from "@odoo/owl";

setup() {
    onMounted(() => {
        this.el = document.querySelector(".my-widget");
        this.el.addEventListener("scroll", this.onScroll);
    });
    onWillUnmount(() => {
        this.el.removeEventListener("scroll", this.onScroll);
    });
}
```

**Why:** The DOM is not available during `setup()`. `onMounted()` fires after the component is rendered and inserted into the DOM. Always pair `onMounted` with `onWillUnmount` for cleanup to prevent memory leaks.

## Reactive State

### Use `useState()` for reactive data

**WRONG:**
```javascript
import { Component } from "@odoo/owl";

export class MyWidget extends Component {
    setup() {
        this.data = [];      // Plain assignment -- not reactive
        this.count = 0;
    }

    increment() {
        this.count++;        // Change won't trigger re-render
    }
}
```

**CORRECT:**
```javascript
import { Component, useState } from "@odoo/owl";

export class MyWidget extends Component {
    setup() {
        this.state = useState({ data: [], count: 0 });
    }

    increment() {
        this.state.count++;  // Triggers re-render
    }
}
```

**Why:** OWL only tracks changes to objects wrapped in `useState()`. Direct property assignments are invisible to the reactivity system and will never trigger a re-render. Always wrap mutable component data in `useState()`.

## RPC Calls

### Use `useService("rpc")` or `useService("orm")` for server calls

**WRONG:**
```javascript
import { Component } from "@odoo/owl";

export class MyWidget extends Component {
    async loadData() {
        // Using fetch() directly -- bypasses Odoo session, CSRF, error handling
        const response = await fetch("/web/dataset/call_kw", {
            method: "POST",
            body: JSON.stringify({ model: "res.partner", method: "search_count" }),
        });
        this.data = await response.json();
    }
}
```

**CORRECT:**
```javascript
import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class MyWidget extends Component {
    setup() {
        this.orm = useService("orm");
    }

    async loadData() {
        this.state.count = await this.orm.searchCount("res.partner", []);
    }
}
```

**Why:** `useService("orm")` and `useService("rpc")` handle session authentication, CSRF tokens, JSON-RPC protocol, and standardized error handling. Direct `fetch()` bypasses all of this, leading to authentication failures and unhandled errors.

## Registry Registration

### Register components in the correct registry category

**WRONG:**
```javascript
import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";

export class MyField extends Component {
    static template = "my_module.MyField";
}

// Global registration -- no category, won't be found
registry.add("my_field", MyField);
```

**CORRECT:**
```javascript
import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";

export class MyField extends Component {
    static template = "my_module.MyField";
    static supportedTypes = ["char"];
}

registry.category("fields").add("my_field", {
    component: MyField,
    supportedTypes: ["char"],
});
```

**Why:** Odoo looks up widgets by registry category. Fields go in `registry.category("fields")`, client actions in `registry.category("actions")`, views in `registry.category("views")`, and systray items in `registry.category("systray")`. A top-level `registry.add()` puts the component nowhere Odoo can find it.

## Event Handling

### Use `t-on-*` directives in templates, not `addEventListener`

**WRONG:**
```javascript
import { Component, onMounted } from "@odoo/owl";

export class MyWidget extends Component {
    setup() {
        onMounted(() => {
            // Manual event binding -- fragile, bypasses OWL event system
            this.el.querySelector(".btn").addEventListener("click", () => {
                this.onClick();
            });
        });
    }

    onClick() {
        console.log("clicked");
    }
}
```

**CORRECT:**
```javascript
import { Component } from "@odoo/owl";

export class MyWidget extends Component {
    static template = "my_module.MyWidget";

    onClick() {
        // handler referenced via t-on-click in template
    }
}
```
```xml
<t t-name="my_module.MyWidget">
    <button class="btn" t-on-click="onClick">Click me</button>
</t>
```

**Why:** `t-on-*` directives are managed by OWL's virtual DOM and are automatically cleaned up on component destruction. Manual `addEventListener` calls require manual cleanup, can reference stale DOM nodes, and break OWL's diffing algorithm.

## Component Props

### Declare `static props` and use `this.props`

**WRONG:**
```javascript
import { Component } from "@odoo/owl";

export class ChildWidget extends Component {
    setup() {
        // Accessing parent directly -- tight coupling, breaks encapsulation
        this.data = this.env.parent.state.data;
        this.record = this.__owl__.parent.props.record;
    }
}
```

**CORRECT:**
```javascript
import { Component } from "@odoo/owl";

export class ChildWidget extends Component {
    static template = "my_module.ChildWidget";
    static props = {
        record: Object,
        onUpdate: { type: Function, optional: true },
    };

    setup() {
        this.data = this.props.record.data;
    }
}
```

**Why:** OWL components communicate via props (parent to child) and events (child to parent). Accessing internal parent state creates fragile coupling that breaks when the parent refactors. Declaring `static props` also enables runtime prop validation in dev mode.

## Service Injection

### Use `useService()` to inject services

**WRONG:**
```javascript
import { Component } from "@odoo/owl";
// Importing the service module directly -- gets the class, not the instance
import { NotificationService } from "@web/core/notifications/notification_service";

export class MyWidget extends Component {
    setup() {
        this.notification = new NotificationService();  // Wrong! No env, no lifecycle
    }
}
```

**CORRECT:**
```javascript
import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class MyWidget extends Component {
    setup() {
        this.notification = useService("notification");
    }

    showMessage() {
        this.notification.add("Hello!", { type: "info" });
    }
}
```

**Why:** `useService()` retrieves the singleton service instance from the OWL environment, properly scoped to the component's lifecycle. Direct imports get the service definition (a factory), not a live instance. Instantiating services manually bypasses dependency injection and lifecycle management.

## Effect Hook

### Use `useEffect()` with cleanup return

**WRONG:**
```javascript
import { Component, onMounted, onWillUnmount } from "@odoo/owl";

export class MyWidget extends Component {
    setup() {
        this.interval = null;
        // Manual setup/cleanup -- verbose, error-prone
        onMounted(() => {
            this.interval = setInterval(() => this.poll(), 5000);
        });
        onWillUnmount(() => {
            clearInterval(this.interval);
        });
    }
}
```

**CORRECT:**
```javascript
import { Component, useState } from "@odoo/owl";
import { useEffect } from "@web/core/utils/hooks";

export class MyWidget extends Component {
    setup() {
        this.state = useState({ active: true });
        useEffect(
            () => {
                const interval = setInterval(() => this.poll(), 5000);
                return () => clearInterval(interval);  // Cleanup returned
            },
            () => [this.state.active]  // Dependencies
        );
    }
}
```

**Why:** `useEffect()` ties side-effect setup and cleanup together, re-runs when dependencies change, and auto-cleans on unmount. Separate `onMounted`/`onWillUnmount` pairs are verbose and don't react to dependency changes, leading to stale closures.

## Template Reference

### Use `static template` with the module-qualified name

**WRONG:**
```javascript
import { Component, xml } from "@odoo/owl";

export class MyWidget extends Component {
    // Inline template string -- won't work in Odoo's asset pipeline
    static template = xml`<div>Hello</div>`;
}
```

**CORRECT:**
```javascript
import { Component } from "@odoo/owl";

export class MyWidget extends Component {
    // References the QWeb template by module-qualified name
    static template = "my_module.MyWidget";
}
```
```xml
<?xml version="1.0" encoding="UTF-8"?>
<templates xml:space="preserve">
    <t t-name="my_module.MyWidget">
        <div>Hello</div>
    </t>
</templates>
```

**Why:** Odoo's asset bundler compiles QWeb templates from XML files and registers them by name. Inline `xml` tagged templates from standalone OWL apps are not supported in Odoo's asset pipeline. The template XML file must be declared in `__manifest__.py` under `assets`.

## Patch Pattern

### Use `patch()` from `@web/core/utils/patch` to extend components

**WRONG:**
```javascript
import { FormController } from "@web/views/form/form_controller";

// Monkey-patching the prototype -- fragile, untracked, breaks on updates
const originalSetup = FormController.prototype.setup;
FormController.prototype.setup = function () {
    originalSetup.call(this);
    this.customField = "hello";
};
```

**CORRECT:**
```javascript
import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";

patch(FormController.prototype, {
    setup() {
        super.setup(...arguments);
        this.customField = "hello";
    },
});
```

**Why:** `patch()` uses Odoo's managed extension system, which supports `super` calls, proper ordering when multiple modules patch the same component, and clean removal. Prototype monkey-patching breaks when patch order changes and makes debugging impossible.

## Common Widget Patterns

### Stat Button Widget

A stat button is a clickable box in a form view's `<div class="oe_button_box">` that
shows a count and navigates to a related list view.

```javascript
export class StatButton extends Component {
    static template = "my_module.StatButton";
    static props = { record: Object };

    setup() {
        this.state = useState({ count: 0 });
        this.orm = useService("orm");
        this.action = useService("action");
        onWillStart(() => this.loadCount());
    }

    async loadCount() {
        this.state.count = await this.orm.searchCount(
            "target.model",
            [["field_id", "=", this.props.record.resId]]
        );
    }

    onClick() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "target.model",
            domain: [["field_id", "=", this.props.record.resId]],
            views: [[false, "list"], [false, "form"]],
        });
    }
}
```

### Dashboard Card Widget

A dashboard card displays aggregated metrics fetched from a controller endpoint.

```javascript
export class DashboardCard extends Component {
    static template = "my_module.DashboardCard";

    setup() {
        this.state = useState({ metrics: {}, loading: true });
        this.rpc = useService("rpc");
        onWillStart(() => this.loadMetrics());
    }

    async loadMetrics() {
        this.state.loading = true;
        this.state.metrics = await this.rpc("/my_module/dashboard/metrics");
        this.state.loading = false;
    }
}
```

### Action Trigger Button

A button that calls a server-side model method and shows a notification.

```javascript
export class ActionButton extends Component {
    static template = "my_module.ActionButton";
    static props = { record: Object };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
    }

    async onClick() {
        try {
            await this.orm.call("target.model", "action_method", [this.props.record.resId]);
            this.notification.add("Action completed", { type: "success" });
        } catch (e) {
            this.notification.add(e.message || "Action failed", { type: "danger" });
        }
    }
}
```

## Registry Categories Reference

| Category | Purpose | Example Use |
|----------|---------|-------------|
| `fields` | Custom field widgets | `registry.category("fields").add("my_widget", { component: MyField })` |
| `actions` | Client actions (full-page views) | `registry.category("actions").add("my_action", MyAction)` |
| `views` | Custom view types | `registry.category("views").add("my_view", myViewDefinition)` |
| `systray` | Systray (top-right) items | `registry.category("systray").add("my_tray", { Component: MyTray })` |
| `main_components` | Root-level persistent components | `registry.category("main_components").add("my_comp", { Component: MyComp })` |
| `services` | Service definitions | `registry.category("services").add("my_service", myServiceDef)` |
| `command_categories` | Command palette categories | `registry.category("command_categories").add("my_cat", { ... })` |
| `command_provider` | Command palette providers | `registry.category("command_provider").add("my_prov", MyProvider)` |

### Registering a custom field widget

```javascript
import { registry } from "@web/core/registry";
import { CharField, charField } from "@web/views/fields/char/char_field";

class MyCharField extends CharField {
    // Custom rendering or behavior
}

registry.category("fields").add("my_char", {
    ...charField,
    component: MyCharField,
});
```

Usage in XML view:
```xml
<field name="my_field" widget="my_char"/>
```

### Registering a client action

```javascript
import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";

class MyDashboard extends Component {
    static template = "my_module.MyDashboard";
}

registry.category("actions").add("my_module.dashboard", MyDashboard);
```

Usage in XML action:
```xml
<record id="action_my_dashboard" model="ir.actions.client">
    <field name="name">My Dashboard</field>
    <field name="tag">my_module.dashboard</field>
</record>
```

## Asset Declaration in Manifest

All JS and XML template files must be declared in `__manifest__.py`:

```python
"assets": {
    "web.assets_backend": [
        "my_module/static/src/components/**/*.js",
        "my_module/static/src/components/**/*.xml",
        "my_module/static/src/components/**/*.scss",
    ],
},
```

**WRONG:** Placing JS files in `static/src/` without declaring them in assets.

**CORRECT:** Every JS/XML/SCSS file under `static/src/` must have a matching glob in `assets`.

**Why:** Odoo's asset bundler only includes files that match globs in the `assets` key. Undeclared files are silently ignored.

---
*Odoo 17.0/18.0/19.0 OWL 2 Components -- loaded by view and widget generation agents*
