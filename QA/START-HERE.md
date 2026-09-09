# Start the BANXUM regression run

Read **Regression-Guide.docx** or **Regression-Guide.md** first. The guide has 78 stories: 33 successful flows, 22 complex flows and 23 edge cases. Registration and superadmin-only cases are excluded; retired story IDs are intentionally not reused.

1. Agree on a staging environment and controlled test accounts. This folder never authorizes production deletion, bank payments or changing real legal terms.
2. Assign the regular Admin and User 1 to User 3 to separate browser profiles. All three investors are already registered. No superadmin account is part of the tester's run.
3. Check **resources/RUN-DATES.md**. Current CSVs start on **2026-09-09**. If your test date differs, refresh them before importing.
4. Use **resources/lo-import-map.csv** as the upload checklist. It states each file's expected result, form values, as-of date, prerequisite and new payment reference. Upload only files inside **valid** or **invalid**; the map and reference worksheets are not imports.
5. Copy **templates/account-setup.csv**, **templates/results.csv** and **templates/bug-report.md** to a private run folder for actual values and results. Their presence is not evidence that a test passed.

## Regression baseline

User 1 and User 2 each start with **CHF 5,000,000 plus EUR 5,000,000**. User 3 is verified but has **zero in both currencies**. Each funded user can close seeded loans alone. No investor password, fabricated legal acceptance or verified payout IBAN is created.

The reset captures a repeatable seed automatically. In staging, Admin opens **QA mode** and uses **Restore seed** to return to that exact seed, including its clock and twenty unfunded loans. QA stays enabled. **Create snapshot** saves an optional later checkpoint; **Restore snapshot** returns to that checkpoint without replacing the seed. Without a manual checkpoint, seed is the default and the snapshot restore button is disabled. Export results first. Restore the seed before incompatible branches, then recreate the guide's small main loans and prerequisites; they are not part of the twenty demo loans.

Actual emails and environment details belong in **local/** (ignored by Git). The owner uses the private mapping with the guarded reset in **docs/runbooks/server-deployment.md**. The generic reset without a mapping retains its separate CHF/EUR 500,000 default.

When a story needs a later date, Admin uses **QA mode** to advance the clock and waits for the scheduled jobs to finish before checking the flows. These controls are available to regular admins in staging and are absent from production. Do not change the device clock or log in as superadmin.

## Resource refresh

From the repository root:

```bash
python3 QA/prepare_resources.py --start-date YYYY-MM-DD --output /tmp/banxum-qa-NEW-RUN
```

Use a real date and a new folder name. The script refuses to overwrite an existing folder. It creates files only, without database or network access. Replace the guide's resource references with the new folder for that run.

## Upload sequence

- Main LO: file 01 creates the draft; file 02 records the boundary; file 03 records the next receipt; file 04 records final payment. Advance the QA clock to each required date before recording it.
- Advance-payment branch: after file 02, use file 05 on a separate copy or restored branch. Do not combine it with the normal file 03 branch.
- Waterfall branch: use the three separate lo-waterfall files on a separate loan.
- Repayment shapes: the four lo-type files create additional drafts. The main loan covers the fifth supported shape.
- Invalid files: apply them only in the mapped phase and starting state. A correct rejection is the pass result.

Every upload contains a complete schedule and, for repayment replacements, the entire prior payment history plus one new receipt. CSVs use integer minor units and ISO dates. Do not let a spreadsheet editor reorder headers, change dates to local formatting or add currency symbols.

## Resources the environment owner must supply

The guide deliberately does not invent secrets or compliance/bank evidence. The owner supplies controlled mailboxes and phones, provider test identities, approved synthetic valid IBANs, collection-account identifiers, role accounts and any API-only/failed-job/aged-balance setup. These values must stay out of Git. An unavailable setup makes the affected story Blocked, not passed.

## Maintaining the guide and files

`prepare_resources.py` uses Python's standard library. `build_guide.py` builds the Word guide and blank results rows from the Markdown source; it requires `python-docx` and the Node `marked` parser. Run it with `--node /path/to/node --marked-module /path/to/marked/lib/marked.esm.js`. Rebuilding replaces only the distributed blank results template, so keep completed results elsewhere.

The supplied files can be checked against the current repository's importer and repayment services without a live database:

```bash
env DATABASE_URL=sqlite:///:memory: .venv/bin/pytest -c pytest.ini QA/tests/test_resources.py -q
```

These checks validate the test data, not a completed manual website regression.

IP of Webby-Soft SRL. See ../NOTICE.md.
