### OTEC Selling

OTEC sales hierarchy, workflow, fulfillment, billing, collection, and workspace customizations

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch version-16
bench install-app otec_selling
```

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/otec_selling
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade
### CI

This app can use GitHub Actions for CI. The following workflows are configured:

- CI: Installs this app and runs unit tests on every push to `develop` branch.
- Linters: Runs [Frappe Semgrep Rules](https://github.com/frappe/semgrep-rules) and [pip-audit](https://pypi.org/project/pip-audit/) on every pull request.


### License

mit

## Phase 6 portability baseline

This repository captures the site-level ERPNext customizations that were previously
stored only in the database. The baseline was exported from the staging site on
2026-08-17 and verified by reinstalling it alongside the existing configuration.

Included fixtures:

- custom DocType definitions;
- relevant Custom Fields, Property Setters, and Custom DocPerm records;
- Selling Client Scripts and Server Scripts;
- Selling workflows, states, and actions;
- Selling workspaces, custom Number Cards, and custom charts;
- custom Selling print formats and roles.

Intentionally excluded:

- User accounts and passwords;
- Sales Access Hierarchy assignments;
- Company, Branch, Warehouse, Customer, Item, and other master records;
- quotations, orders, fulfillment, stock, invoice, payment, GL, and serial records;
- site configuration, encryption keys, API secrets, and file attachments.

### Safe deployment sequence

1. Take a complete site backup.
2. Add this repository to the Frappe Cloud bench on branch `version-16`.
3. Install `otec_selling` on a staging clone first.
4. Run `bench --site <site> migrate` through the managed Frappe Cloud deployment.
5. Execute the hierarchy, workflow, fulfillment, billing, and collection matrices.
6. Disable a database Server Script or Client Script only after its app-code
   replacement has passed parity testing.

The current baseline deliberately keeps database scripts enabled. Fixtures provide
recoverability and version history; they do not yet replace the script runtime with
Python hooks or bundled JavaScript.
