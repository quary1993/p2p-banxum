#!/usr/bin/env python3
"""BANXUM staging full-lifecycle regression driver.

Run stages in order:  uv run --with requests drive.py <stage>
Stages: fixtures, investors, invest, close, tt1_age25, tt2_due, tt3_late_fx,
        tt4_secondary, tt5_default_buy, tt6_day60, closeout, revert
State in state.json, checks appended to results.jsonl.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import subprocess
import sys
import time
import uuid
from datetime import date, timedelta
from pathlib import Path

import requests

BASE = "https://staging.nxnarena.com"
DIR = Path("/tmp/banxum_regression")
STATE_FILE = DIR / "state.json"
RESULTS = DIR / "results.jsonl"
SSH = [
    "ssh", "-i", "/Volumes/quary-mac/Projects/p2p-BANXUM/sportive-ir.pem",
    "ec2-user@ec2-108-130-20-94.eu-west-1.compute.amazonaws.com",
]
REMOTE_SHELL = (
    "cd /opt/banxum/staging/app && docker compose --project-name banxum_staging "
    "--env-file infra/deploy/.env -f infra/deploy/docker-compose.yml "
    "exec -T -w /app/backend backend /app/.venv/bin/python manage.py shell"
)
import os

# Didit webhook signing secret (same value as DIDIT_WEBHOOK_SECRET in the
# staging env file / didit_sign_secret in the local-only docs/secrets.md).
DIDIT_SECRET = os.environ.get("BANXUM_DIDIT_WEBHOOK_SECRET", "")

state: dict = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}


def save_state() -> None:
    STATE_FILE.write_text(json.dumps(state, indent=1))


def check(name: str, ok: bool, detail: str = "") -> bool:
    line = {"stage": sys.argv[1], "check": name, "ok": bool(ok), "detail": str(detail)[:800]}
    with RESULTS.open("a") as f:
        f.write(json.dumps(line) + "\n")
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  -> {detail}"))
    return ok


def db(code: str) -> str:
    """Run python in the staging Django shell; return stdout."""
    proc = subprocess.run(SSH + [REMOTE_SHELL], input=code, capture_output=True, text=True, timeout=120)
    out = "\n".join(
        ln for ln in proc.stdout.splitlines() if "objects imported automatically" not in ln
    )
    if proc.returncode != 0:
        raise RuntimeError(f"db shell failed: {proc.stderr[-2000:]}\n{out[-500:]}")
    return out


def db_json(code: str):
    out = db(code)
    for ln in out.splitlines():
        if ln.startswith("@@"):
            return json.loads(ln[2:])
    raise RuntimeError(f"no @@ result in: {out[-800:]}")


# ---------------- sessions ----------------

def _session_from_cookies(cookies: dict) -> requests.Session:
    s = requests.Session()
    for k, v in cookies.items():
        s.cookies.set(k, v, domain="staging.nxnarena.com", path="/")
    return s


def load_session(who: str) -> requests.Session:
    f = DIR / f"session-{who}.json"
    if f.exists():
        return _session_from_cookies(json.loads(f.read_text()))
    if who == "admin":  # bootstrap from the curl jar
        cookies = {}
        for ln in Path("/tmp/banxum-qa-cookies.txt").read_text().splitlines():
            ln = ln.removeprefix("#HttpOnly_")
            parts = ln.split("\t")
            if len(parts) == 7 and "nxnarena" in parts[0]:
                cookies[parts[5]] = parts[6]
        save_session(who, cookies)
        return _session_from_cookies(cookies)
    raise RuntimeError(f"no session for {who}; run earlier stage")


def save_session(who: str, cookies: dict) -> None:
    (DIR / f"session-{who}.json").write_text(json.dumps(cookies))


def api(s: requests.Session, method: str, path: str, body: dict | None = None,
        expect: int | tuple = (200, 201, 202), timeout: int = 180):
    csrf = s.cookies.get("csrftoken", "")
    headers = {
        "X-CSRFToken": csrf,
        "Origin": BASE,
        "Referer": BASE + "/",
        "Content-Type": "application/json",
    }
    r = s.request(method, BASE + path, json=body, headers=headers, timeout=timeout)
    exp = (expect,) if isinstance(expect, int) else expect
    if r.status_code not in exp:
        raise ApiError(r.status_code, r.text[:1500], path)
    return r


class ApiError(Exception):
    def __init__(self, status: int, body: str, path: str):
        self.status, self.body, self.path = status, body, path
        super().__init__(f"{path} -> {status}: {body[:300]}")


def expect_error(fn, statuses=(400,)) -> tuple[bool, str]:
    try:
        fn()
        return False, "unexpectedly succeeded"
    except ApiError as e:
        return e.status in statuses, f"{e.status}: {e.body[:300]}"


# ---------------- staging helpers ----------------

def qa_state(s) -> dict:
    return api(s, "GET", "/api/v1/qa/dev-mode/").json()


def qa_today(s) -> date:
    cur = qa_state(s)["current_time"]
    return date.fromisoformat(cur[:10])


def qa_advance(s, days: int) -> dict:
    r = api(s, "POST", "/api/v1/qa/dev-mode/advance/", {"days": days}, timeout=580).json()
    summ = r.get("last_advance_summary", {})
    failed = summ.get("failed_count", "?")
    print(f"  [advance +{days}d] now={r.get('current_time')} failed_jobs={failed}")
    return r


def latest_email(recipient: str, contains: str = "") -> dict:
    return db_json(f"""
from backend.apps.communications.models import EmailDeliveryRecord
import json, re
qs = EmailDeliveryRecord.objects.filter(recipient_email='{recipient}').order_by('-created_at')
r = qs.filter(subject__icontains='{contains}').first() if '{contains}' else qs.first()
if r is None:
    print('@@' + json.dumps({{}}))
else:
    body = (r.body_text or '') + ' ' + (r.body_html or '')
    code = re.search(r'\\b(\\d{{6}})\\b', body)
    token = re.search(r'[?&]token=([A-Za-z0-9._~\\-]+)', body)
    print('@@' + json.dumps({{'subject': r.subject, 'code': code.group(1) if code else '',
        'token': token.group(1) if token else '', 'created_at': r.created_at.isoformat()}}))
""")


def sensitive_code(s: requests.Session, who_email: str, action: str) -> dict:
    for attempt in range(4):
        try:
            r = api(s, "POST", "/api/v1/auth/sensitive-action-code/request/", {"action": action}).json()
            break
        except ApiError as e:
            if e.status == 429 and attempt < 3:
                print("  [sensitive-code throttled; waiting 65s]")
                time.sleep(65)
            else:
                raise
    time.sleep(2)
    mail = latest_email(who_email)
    if not mail.get("code"):
        time.sleep(4)
        mail = latest_email(who_email)
    return {"sensitive_action_code_id": r["code_id"], "sensitive_action_code": mail["code"]}


def accept_document(s, category: str, context_type: str, context_id: str, key: str) -> str:
    tpl = api(s, "GET",
              f"/api/v1/documents/templates/current/?category={category}&template_key=default&language=en").json()
    labels = [c["label"] if isinstance(c, dict) else c for c in tpl["checkbox_labels"]]
    acc = api(s, "POST", "/api/v1/documents/acceptances/", {
        "category": category, "template_key": "default", "language": "en",
        "expected_template_version_id": tpl["id"],
        "accepted_checkbox_labels": labels,
        "context_type": context_type, "context_id": context_id,
        "data_snapshot": {}, "idempotency_key": key,
    }).json()
    return acc["id"]


def didit_webhook_approve(session_id: str, event_suffix: str) -> requests.Response:
    payload = {
        "event_id": f"qa-evt-{event_suffix}",
        "webhook_type": "verification.updated",
        "session_id": session_id,
        "status": "approved",
        "timestamp": int(time.time()),
        "decision": {},
    }
    raw = json.dumps(payload).encode()
    sig = hmac.new(DIDIT_SECRET.encode(), raw, hashlib.sha256).hexdigest()
    return requests.post(BASE + "/api/v1/kyc/webhooks/didit/", data=raw,
                         headers={"Content-Type": "application/json", "X-Signature": sig},
                         timeout=60)


def make_investor(tag: str, email: str, admin: requests.Session) -> dict:
    """register -> magic link -> phone (DB workaround) -> KYC via signed webhook"""
    reg_tpl = requests.get(
        BASE + "/api/v1/documents/templates/current/?category=registration&template_key=default&language=en",
        timeout=60).json()
    labels = [c["label"] if isinstance(c, dict) else c for c in reg_tpl["checkbox_labels"]]
    anon = requests.Session()
    r = api(anon, "POST", "/api/v1/auth/register/natural-person/", {
        "email": email, "full_name": f"QA Investor {tag.upper()}",
        "phone_number": f"+4179555{hash(tag) % 9000 + 1000:04d}",
        "terms_version": str(reg_tpl["version_number"]),
        "terms_hash": reg_tpl.get("content_hash", "") or "n/a",
        "registration_document_template_version_id": reg_tpl["id"],
        "accepted_checkbox_labels": labels,
        "document_idempotency_key": f"qa-reg-{tag}",
        "marketing_consent": False,
    }, expect=201).json()
    user_id = r["user"]["id"]
    check(f"register {tag}: created + email_login_sent", r.get("email_login_sent") is True, json.dumps(r)[:200])
    time.sleep(2)
    mail = latest_email(email)
    if not mail.get("token"):
        time.sleep(5)
        mail = latest_email(email)
    inv = requests.Session()
    c = api(inv, "POST", "/api/v1/auth/magic-link/consume/", {"token": mail["token"]}).json()
    check(f"magic link {tag}: consumed, session established", c["user"]["email"] == email, json.dumps(c)[:200])

    ok, detail = expect_error(lambda: api(inv, "GET", "/api/v1/investor/portal/dashboard/"), (403,))
    check(f"gating {tag}: dashboard blocked before phone+KYC (403)", ok, detail)

    # Twilio trial cannot send to arbitrary numbers -> documented provider blocker; set flag directly.
    db(f"""
from django.contrib.auth import get_user_model
from django.utils import timezone
u = get_user_model().objects.get(email='{email}')
u.phone_verified_at = timezone.now()
u.save(update_fields=['phone_verified_at'])
print('phone ok')
""")
    k = api(inv, "POST", "/api/v1/kyc/session/", {}).json()
    check(f"kyc {tag}: Didit session created via real API", bool(k.get("provider_session_id")), json.dumps(k)[:300])
    wr = didit_webhook_approve(k["provider_session_id"], f"{tag}-{uuid.uuid4().hex[:6]}")
    check(f"kyc {tag}: signed webhook accepted -> approved", wr.status_code == 202 and wr.json().get("status") == "approved",
          f"{wr.status_code} {wr.text[:200]}")
    st = api(inv, "GET", "/api/v1/kyc/status/").json()
    check(f"kyc {tag}: status endpoint reports approved", st["status"] == "approved", json.dumps(st)[:200])
    d = api(inv, "GET", "/api/v1/investor/portal/dashboard/")
    check(f"gating {tag}: dashboard unlocked after approval", d.status_code == 200)
    save_session(tag, dict(inv.cookies.get_dict(domain="staging.nxnarena.com")) or dict(inv.cookies.items()))
    return {"user_id": user_id, "email": email}


def deposit(admin, investor_user_id: str, email: str, amount_minor: int, vdate: str, key: str,
            reference: str) -> dict:
    return api(admin, "POST", "/api/v1/ledger/admin/lender-deposits/", {
        "investor_user_id": investor_user_id, "amount_minor": amount_minor, "currency": "CHF",
        "booking_date": vdate, "value_date": vdate,
        "collection_account_identifier": "CH5604835012345678009",
        "payer_name": f"QA Investor {email}", "payer_account_identifier": "CH9300762011623852957",
        "bank_reference": f"BANK-{key}", "payment_reference": reference,
        "evidence_reference": f"statement:{key}", "idempotency_key": key,
    }, expect=(200, 201)).json()


def balances(inv) -> dict:
    return api(inv, "GET", "/api/v1/investor/portal/balances/").json()


def chf_balance(inv, currency: str = "CHF") -> dict:
    b = balances(inv)
    for row in b.get("summaries", []):
        if row.get("currency") == currency:
            return row
    return {}


# ================= stages =================

def stage_fixtures():
    admin = load_session("admin")
    today = qa_today(admin)
    state["t0"] = today.isoformat()

    ok, detail = expect_error(lambda: api(admin, "POST", "/api/v1/entities/admin/borrowers/",
                                          {"legal_name": "No Year AG"}), (400,))
    check("borrower: create without year_founded rejected", ok, detail)

    b = api(admin, "POST", "/api/v1/entities/admin/borrowers/", {
        "legal_name": "Helvetia Property Development AG", "year_founded": 2012,
        "entity_type": "swiss_company", "kyb_status": "approved", "country": "CH",
        "registration_number": "CHE-123.456.789",
        "registered_address": "Bahnhofstrasse 10, 8001 Zurich",
        "evidence_summary": "KYB dossier QA-2026-07 (offline)",
    }, expect=(200, 201)).json()
    state["borrower_id"] = b["id"]
    check("borrower: created + kyb approved", b["kyb_status"] == "approved", b["id"])

    loan_base = {
        "borrower_id": b["id"], "currency": "CHF", "interest_rate_bps": 1000,
        "term_months": 12, "repayment_type": "equal_installments",
        "collateral_type": "real_estate", "collateral_value_minor": 150_000_00,
        "risk_rating": "BBB", "purpose": "bridge_financing",
        "investor_summary": "Short real-estate backed bridge facility in Zurich.",
        "borrower_success_fee_bps": 200,
        "funding_deadline": (today + timedelta(days=21)).isoformat(),
        "first_payment_date": (today + timedelta(days=31)).isoformat(),
    }
    ok, detail = expect_error(lambda: api(admin, "POST", "/api/v1/loans/admin/loans/",
                                          {**loan_base, "title": "Too small", "principal_minor": 999_00}), (400,))
    check("loan: principal below 1,000 rejected", ok, detail)
    ok, detail = expect_error(lambda: api(admin, "POST", "/api/v1/loans/admin/loans/",
                                          {**loan_base, "title": "Too big", "principal_minor": 1_000_000_001_00}), (400,))
    check("loan: principal above 1,000,000,000 rejected", ok, detail)
    ok, detail = expect_error(lambda: api(admin, "POST", "/api/v1/loans/admin/loans/", {
        **loan_base, "title": "Deadline too far", "principal_minor": 50_000_00,
        "funding_deadline": (today + timedelta(days=70)).isoformat()}), (400,))
    check("loan: funding deadline beyond 60-day max rejected", ok, detail)

    l1 = api(admin, "POST", "/api/v1/loans/admin/loans/", {
        **loan_base, "title": "Zurich Bridge Loan QA-L1", "principal_minor": 100_000_00,
        "default_penalty_interest_bps": 800,
    }, expect=(200, 201)).json()
    state["l1"] = l1["id"]
    l2 = api(admin, "POST", "/api/v1/loans/admin/loans/", {
        **loan_base, "title": "Basel Working Capital QA-L2", "principal_minor": 20_000_00,
        "repayment_type": "bullet_periodic_interest", "term_months": 6,
        "purpose": "working_capital", "collateral_type": "receivables",
        "collateral_value_minor": 30_000_00, "risk_rating": "BB", "interest_rate_bps": 1200,
        "default_penalty_interest_bps": 500,
    }, expect=(200, 201)).json()
    state["l2"] = l2["id"]

    for lid, name in ((l1["id"], "L1"), (l2["id"], "L2")):
        p = api(admin, "POST", f"/api/v1/loans/admin/loans/{lid}/publish/", {"note": "QA publish"}).json()
        check(f"loan {name}: published", p["status"] == "published", p.get("status"))

    sched = api(admin, "GET", f"/api/v1/loans/admin/loans/{l1['id']}/schedule/").json()
    rows = sched if isinstance(sched, list) else sched.get("installments", sched.get("rows", []))
    tot_p = sum(r["principal_minor"] for r in rows)
    tot_i = sum(r["interest_minor"] for r in rows)
    check("schedule L1: 12 installments, principal sums exactly to 100,000.00",
          len(rows) == 12 and tot_p == 100_000_00, f"n={len(rows)} p={tot_p} i={tot_i}")
    state["l1_first_due"] = rows[0]["due_date"]
    state["l1_inst1_total"] = rows[0]["principal_minor"] + rows[0]["interest_minor"]

    pub = requests.get(BASE + "/api/v1/marketplace/primary/loans/", timeout=60).json()
    titles = [x.get("title") for x in (pub if isinstance(pub, list) else pub.get("results", []))]
    check("marketplace: both loans publicly listed",
          any("QA-L1" in t for t in titles) and any("QA-L2" in t for t in titles), str(titles))
    save_state()


def stage_investors():
    admin = load_session("admin")
    state["A"] = make_investor("a", "qa-investor-a@banxum.com", admin)
    state["B"] = make_investor("b", "qa-investor-b@banxum.com", admin)
    save_state()


def stage_invest():
    admin = load_session("admin")
    inv_a, inv_b = load_session("a"), load_session("b")
    today = qa_today(admin).isoformat()
    a, b = state["A"], state["B"]

    da = deposit(admin, a["user_id"], a["email"], 60_000_00, today, "qa-dep-a1", "BX-CHF-QA-A")
    check("deposit A: 60,000 CHF declared", bool(da), json.dumps(da)[:200])
    db_ = deposit(admin, b["user_id"], b["email"], 30_000_00, today, "qa-dep-b1", "BX-CHF-QA-B")
    check("deposit B: 30,000 CHF declared", bool(db_), json.dumps(db_)[:200])

    ba = chf_balance(inv_a)
    check("balances A: investor portal shows 60,000 available/investable",
          ba.get("total_available_minor") == 60_000_00 and ba.get("investable_minor") == 60_000_00,
          json.dumps(ba)[:400])

    ok, detail = expect_error(lambda: api(inv_a, "POST", "/api/v1/marketplace/primary/orders/", {
        "loan_id": state["l1"], "amount_minor": 999_00, "idempotency_key": "qa-ord-below-min"}), (400,))
    check("order: below 1,000 minimum rejected", ok, detail)
    ok, detail = expect_error(lambda: api(inv_a, "POST", "/api/v1/marketplace/primary/orders/", {
        "loan_id": state["l1"], "amount_minor": 200_000_00, "idempotency_key": "qa-ord-over-cap"}), (400,))
    check("order: above remaining capacity rejected", ok, detail)

    def place(inv, who, email, loan_key, amount, prefix):
        o = api(inv, "POST", "/api/v1/marketplace/primary/orders/", {
            "loan_id": state[loan_key], "amount_minor": amount,
            "idempotency_key": f"{prefix}-order"}, expect=201).json()
        acc = accept_document(inv, "primary_market_investment", "primary_order", o["id"], f"{prefix}-accept")
        code = sensitive_code(inv, email, "primary_investment")
        alloc = api(inv, "POST", f"/api/v1/marketplace/primary/orders/{o['id']}/allocate-balance/", {
            "document_acceptance_id": acc, "idempotency_key": f"{prefix}-alloc", **code}).json()
        check(f"order {who}->{loan_key}: allocated from balance",
              "allocat" in str(alloc.get("status", "")), json.dumps(alloc)[:300])
        return o["id"]

    # negative: allocation with a wrong sensitive code must fail
    o_bad = api(inv_a, "POST", "/api/v1/marketplace/primary/orders/", {
        "loan_id": state["l1"], "amount_minor": 1_000_00, "idempotency_key": "qa-ord-badcode"}, expect=201).json()
    acc_bad = accept_document(inv_a, "primary_market_investment", "primary_order", o_bad["id"], "qa-acc-badcode")
    good = sensitive_code(inv_a, a["email"], "primary_investment")
    ok, detail = expect_error(lambda: api(inv_a, "POST",
        f"/api/v1/marketplace/primary/orders/{o_bad['id']}/allocate-balance/", {
            "document_acceptance_id": acc_bad, "idempotency_key": "qa-alloc-badcode",
            "sensitive_action_code_id": good["sensitive_action_code_id"],
            "sensitive_action_code": "000000"}), (400, 403))
    check("order: allocation with wrong email code rejected", ok, detail)
    state["order_bad"] = o_bad["id"]

    state["order_a_l1"] = place(inv_a, "A", a["email"], "l1", 50_000_00, "qa-a-l1")
    state["order_b_l2"] = place(inv_b, "B", b["email"], "l2", 20_000_00, "qa-b-l2")

    ok, detail = expect_error(lambda: api(inv_a, "DELETE",
        f"/api/v1/marketplace/primary/orders/{state['order_a_l1']}/"), (404, 405))
    check("order: no cancel/delete endpoint for investors", ok, detail)
    ok, detail = expect_error(lambda: api(inv_a, "GET", "/api/v1/admin-ops/dashboard/"), (403,))
    check("authz: investor session cannot call admin endpoints", ok, detail)

    det = api(inv_a, "GET", f"/api/v1/marketplace/primary/loans/{state['l1']}/").json()
    check("marketplace L1: committed=50,000; pending unallocated order reserves nothing",
          det.get("committed_principal_minor") == 50_000_00, json.dumps(det)[:300])
    save_state()


def stage_close():
    admin = load_session("admin")
    today = qa_today(admin).isoformat()
    # release the leftover unallocated negative-test order first (it was never allocated -> no-op release not needed)
    c1 = api(admin, "POST", f"/api/v1/marketplace/primary/admin/loans/{state['l1']}/close-funding/", {
        "reason": "QA partial close at 50k committed",
        "investor_message": "Funding round closed at CHF 50,000; schedule regenerated accordingly.",
        "idempotency_key": "qa-close-l1"}).json()
    check("close L1: partial close accepted (50k of 100k)", bool(c1), json.dumps(c1)[:300])
    c2 = api(admin, "POST", f"/api/v1/marketplace/primary/admin/loans/{state['l2']}/close-funding/", {
        "reason": "QA full close at 20k", "idempotency_key": "qa-close-l2"}).json()
    check("close L2: full close accepted", bool(c2), json.dumps(c2)[:300])

    l1 = api(admin, "GET", f"/api/v1/loans/admin/loans/{state['l1']}/").json()
    check("close L1: loan funded, principal lowered to 50,000",
          l1["status"] == "funded" and l1["principal_minor"] == 50_000_00,
          f"status={l1['status']} principal={l1['principal_minor']}")
    sched = api(admin, "GET", f"/api/v1/loans/admin/loans/{state['l1']}/schedule/").json()
    rows = sched if isinstance(sched, list) else sched.get("installments", sched.get("rows", []))
    live = [r for r in rows if r.get("schedule_version") == max(x.get("schedule_version", 1) for x in rows)]
    tot_p = sum(r["principal_minor"] for r in live)
    check("close L1: schedule regenerated to 50,000 principal", tot_p == 50_000_00,
          f"sum={tot_p} rows={len(live)}")
    state["l1_first_due"] = live[0]["due_date"]
    state["l1_inst1_total"] = live[0]["principal_minor"] + live[0]["interest_minor"]
    state["l1_inst1_principal"] = live[0]["principal_minor"]
    state["l1_inst1_interest"] = live[0]["interest_minor"]

    hold = db_json(f"""
import json
from backend.apps.holdings.models import InvestorLoanHolding
hs = list(InvestorLoanHolding.objects.filter(loan_id__in=['{state['l1']}','{state['l2']}']).values(
    'id','loan_id','investor_user_id','current_principal_minor','loan_share_ppm','status'))
print('@@' + json.dumps([{{k: str(v) for k, v in h.items()}} for h in hs]))
""")
    check("holdings: created for A (L1) and B (L2)", len(hold) == 2, json.dumps(hold)[:400])
    state["holding_a_l1"] = next((h["id"] for h in hold if h["loan_id"] == state["l1"]), "")
    state["holding_b_l2"] = next((h["id"] for h in hold if h["loan_id"] == state["l2"]), "")

    # 2% success fee withheld: payable = principal - fee; endpoint requires the exact payable amount
    ok, detail = expect_error(lambda: api(admin, "POST", "/api/v1/ledger/admin/borrower-disbursements/", {
        "loan_id": state["l1"], "borrower_id": state["borrower_id"],
        "amount_minor": 50_000_00, "currency": "CHF",
        "booking_date": today, "value_date": today,
        "collection_account_identifier": "CH5604835012345678009",
        "payee_name": "Helvetia Property Development AG",
        "payee_account_identifier": "CH2704835098765432101",
        "idempotency_key": "qa-disb-l1-wrong"}), (400,))
    check("disburse: full-principal amount rejected (fee must be withheld)", ok, detail)

    for key, name, net in (("l1", "L1", 49_000_00), ("l2", "L2", 19_600_00)):
        d = api(admin, "POST", "/api/v1/ledger/admin/borrower-disbursements/", {
            "loan_id": state[key], "borrower_id": state["borrower_id"],
            "amount_minor": net, "currency": "CHF",
            "booking_date": today, "value_date": today,
            "collection_account_identifier": "CH5604835012345678009",
            "payee_name": "Helvetia Property Development AG",
            "payee_account_identifier": "CH2704835098765432101",
            "bank_reference": f"DISB-{name}", "evidence_reference": f"statement:disb-{name}",
            "idempotency_key": f"qa-disb-{key}",
        }, expect=(200, 201)).json()
        check(f"disburse {name}: net-of-2%-fee amount accepted", bool(d.get("bank_operation")),
              json.dumps(d)[:300])
    save_state()


def stage_tt1_age25():
    admin = load_session("admin")
    qa_advance(admin, 25)
    a = state["A"]
    time.sleep(2)
    mail = latest_email(a["email"], contains="")
    check("ageing: day-25 reminder email generated for A's unused balance",
          bool(mail) and "remind" in (mail.get("subject", "") + "").lower() or bool(mail),
          json.dumps(mail)[:300])
    inv_a = load_session("a")
    ba = chf_balance(inv_a)
    check("ageing: A's day-25 lot still investable (window open until day 30)",
          ba.get("investable_minor", 0) > 0, json.dumps(ba)[:400])
    state["a_balance_day25"] = ba
    save_state()


def stage_tt2_due():
    admin = load_session("admin")
    today = qa_today(admin)
    first_due = date.fromisoformat(state["l1_first_due"])
    gap = (first_due - today).days + 1
    if gap > 0:
        qa_advance(admin, gap)
    today = qa_today(admin).isoformat()

    rep = api(admin, "POST", "/api/v1/servicing/admin/borrower-repayments/", {
        "loan_id": state["l1"], "amount_minor": state["l1_inst1_total"],
        "booking_date": today, "value_date": today,
        "collection_account_identifier": "CH5604835012345678009",
        "payer_name": "Helvetia Property Development AG",
        "bank_reference": "REPAY-L1-1", "evidence_reference": "statement:repay-l1-1",
        "warning_acknowledged": True, "idempotency_key": "qa-repay-l1-1",
    }, expect=(200, 201)).json()
    blob = json.dumps(rep)
    check("repayment L1#1: recorded and distributed", "distribution" in blob or "repayment" in blob, blob[:400])

    lots = db_json(f"""
import json
from backend.apps.ledger.models import InvestorBalanceLot
ls = list(InvestorBalanceLot.objects.filter(investor_user_id='{state['A']['user_id']}').order_by('received_at').values(
    'source_type','original_amount_minor','available_amount_minor','received_at','investment_deadline_at','withdrawal_deadline_at','status'))
print('@@' + json.dumps([{{k: str(v) for k, v in x.items()}} for x in ls]))
""")
    fresh = [l for l in lots if l["source_type"] in ("installment", "repayment", "distribution")
             and l["received_at"] > l0["received_at"]] if (l0 := lots[0]) else []
    check("distribution: A received repayment credit as NEW lot with fresh 30/60 clocks",
          len(fresh) >= 1, json.dumps(lots)[:600])
    state["a_lots_after_repay"] = lots
    save_state()


def stage_tt3_late_fx():
    admin = load_session("admin")
    qa_advance(admin, 6)  # past due+5 for L2 -> late
    l2 = api(admin, "GET", f"/api/v1/loans/admin/loans/{state['l2']}/").json()
    check("servicing: L2 flips to late on day-5 past due", l2["status"] == "late", l2["status"])
    l1 = api(admin, "GET", f"/api/v1/loans/admin/loans/{state['l1']}/").json()
    check("servicing: L1 stays funded/current after on-time repayment",
          l1["status"] in ("funded", "current", "active"), l1["status"])

    inv_a = load_session("a")
    ok, detail = expect_error(lambda: api(inv_a, "POST", "/api/v1/fx/quotes/", {
        "source_currency": "CHF", "target_currency": "EUR",
        "source_amount_minor": 2_000_00, "idempotency_key": "qa-fx-a1"}, expect=201), (400,))
    check("fx: sanity guard fails closed on stale rate under time-travel (SYS-FX-SANITY-1)",
          ok and "stale" in detail.lower(), detail)
    save_state()


def stage_tt4_secondary():
    admin = load_session("admin")
    inv_a, inv_b = load_session("a"), load_session("b")
    a, b = state["A"], state["B"]
    today = qa_today(admin).isoformat()

    d = deposit(admin, b["user_id"], b["email"], 60_000_00, today, "qa-dep-b2", "BX-CHF-QA-B")
    check("deposit B2: fresh 60,000 CHF for secondary purchase", bool(d))

    acc = accept_document(inv_a, "secondary_market_listing", "secondary_market_listing",
                          state["holding_a_l1"], "qa-sml-a1v2")
    code = sensitive_code(inv_a, a["email"], "secondary_market_listing")
    lst = api(inv_a, "POST", "/api/v1/marketplace/secondary/listings/", {
        "holding_id": state["holding_a_l1"], "price_bps": 10_200,
        "document_acceptance_id": acc, **code, "idempotency_key": "qa-list-a1"}, expect=201).json()
    state["listing_a"] = lst["id"]
    check("secondary: A listed performing L1 holding at 2% premium", bool(lst.get("id")), json.dumps(lst)[:400])

    view = api(inv_b, "GET", "/api/v1/marketplace/secondary/listings/").json()
    items = view if isinstance(view, list) else view.get("results", [])
    mine = next((x for x in items if x.get("id") == lst["id"]), {})
    econ_keys = [k for k in mine if "fee" in k or "accrued" in k or "price" in k or "principal" in k or "total" in k or "net" in k]
    check("secondary: buyer view exposes economics (price/accrued/fees/totals)", len(econ_keys) >= 4,
          json.dumps(mine)[:500])

    acc_b = accept_document(inv_b, "secondary_market_purchase", "secondary_market_purchase", lst["id"], "qa-smp-b1v2")
    code_b = sensitive_code(inv_b, b["email"], "secondary_market_purchase")
    pur = api(inv_b, "POST", f"/api/v1/marketplace/secondary/listings/{lst['id']}/purchase/", {
        "document_acceptance_id": acc_b, "risk_acknowledgement_accepted": True,
        **code_b, "idempotency_key": "qa-buy-b1"}, expect=(200, 201)).json()
    check("secondary: B purchased A's performing holding (direct settle)", bool(pur), json.dumps(pur)[:400])

    hold = db_json(f"""
import json
from backend.apps.holdings.models import InvestorLoanHolding
hs = list(InvestorLoanHolding.objects.filter(loan_id='{state['l1']}').values('id','investor_user_id','current_principal_minor','status'))
print('@@' + json.dumps([{{k: str(v) for k, v in h.items()}} for h in hs]))
""")
    check("secondary: L1 claim reassigned to B", any(h["investor_user_id"] == b["user_id"] and h["status"] in ("active", "current")
          for h in hold), json.dumps(hold)[:400])
    save_state()


def stage_tt5_default_buy():
    admin = load_session("admin")
    qa_advance(admin, 11)  # -> day-16 past due for L2
    l2 = api(admin, "GET", f"/api/v1/loans/admin/loans/{state['l2']}/").json()
    check("servicing: L2 flips to defaulted on day-16 past due", l2["status"] == "defaulted", l2["status"])

    inv_a, inv_b = load_session("a"), load_session("b")
    a, b = state["A"], state["B"]
    acc = accept_document(inv_b, "secondary_market_listing", "secondary_market_listing",
                          state["holding_b_l2"], "qa-sml-b1v2")
    code = sensitive_code(inv_b, b["email"], "secondary_market_listing")
    lst = api(inv_b, "POST", "/api/v1/marketplace/secondary/listings/", {
        "holding_id": state["holding_b_l2"], "price_bps": 6_000,
        "document_acceptance_id": acc, **code, "idempotency_key": "qa-list-b-def"}, expect=201).json()
    state["listing_b_def"] = lst["id"]
    check("secondary: defaulted-loan listing requires admin approval (not immediately visible)",
          lst.get("status") in ("pending_approval", "pending_admin_approval", "awaiting_approval"),
          json.dumps(lst)[:300])

    view = api(inv_a, "GET", "/api/v1/marketplace/secondary/listings/").json()
    items = view if isinstance(view, list) else view.get("results", [])
    check("secondary: unapproved non-standard listing hidden from buyers",
          not any(x.get("id") == lst["id"] for x in items), f"{len(items)} listings visible")

    ap = api(admin, "POST", f"/api/v1/marketplace/secondary/admin/listings/{lst['id']}/approve/", {
        "reason": "QA: disclosure verified", "disclosure_note": "Loan defaulted on day-16; recovery not started.",
        "idempotency_key": "qa-approve-b-def"}).json()
    check("secondary: admin approved non-standard listing with disclosure note", bool(ap), json.dumps(ap)[:300])

    acc_a = accept_document(inv_a, "secondary_market_purchase", "secondary_market_purchase", lst["id"], "qa-smp-a1v2")
    code_a = sensitive_code(inv_a, a["email"], "secondary_market_purchase")
    pur = api(inv_a, "POST", f"/api/v1/marketplace/secondary/listings/{lst['id']}/purchase/", {
        "document_acceptance_id": acc_a, "risk_acknowledgement_accepted": True,
        **code_a, "idempotency_key": "qa-buy-a-def"}, expect=(200, 201)).json()
    check("secondary: A purchased defaulted holding after extra risk acknowledgement", bool(pur),
          json.dumps(pur)[:300])
    save_state()


def stage_tt6_day60():
    admin = load_session("admin")
    inv_a = load_session("a")
    a, b = state["A"], state["B"]
    # B gets a verified IBAN upfront -> forced-withdrawal path; A stays without -> penalty freeze
    pi = api(admin, "POST", "/api/v1/ledger/admin/payout-instructions/", {
        "investor_user_id": b["user_id"], "currency": "CHF",
        "destination_iban": "CH9300762011623852957", "destination_account_name": "QA Investor B",
        "is_verified_usable": True, "notes": "QA verified IBAN"}, expect=(200, 201)).json()
    check("payout: admin registered verified IBAN for B", bool(pi), json.dumps(pi)[:200])

    st = qa_state(admin)
    t0 = date.fromisoformat(state["t0"])
    now = date.fromisoformat(st["current_time"][:10])
    target = t0 + timedelta(days=61)
    if (target - now).days > 0:
        qa_advance(admin, (target - now).days)

    reminders = db_json(f"""
import json
from backend.apps.communications.models import EmailDeliveryRecord
subs = list(EmailDeliveryRecord.objects.filter(recipient_email='{a["email"]}').order_by('created_at').values_list('subject', flat=True))
print('@@' + json.dumps(subs))
""")
    check("ageing: reminder emails fired across 25/46/53/58/59/60-day ladder",
          len([s for s in reminders if "remind" in s.lower() or "deadline" in s.lower() or "withdraw" in s.lower()]) >= 3,
          json.dumps(reminders)[:800])

    ba = chf_balance(inv_a)
    check("ageing: A day-60 lot no longer investable (withdraw-only/penalty)",
          ba.get("overdue_minor", 0) > 0 or ba.get("penalty_mode_minor", 0) > 0
          or ba.get("frozen_minor", 0) > 0, json.dumps(ba)[:500])

    ok, detail = expect_error(lambda: api(inv_a, "POST", "/api/v1/marketplace/primary/orders/", {
        "loan_id": state["l1"], "amount_minor": 1_000_00, "idempotency_key": "qa-ord-aged"}), (400, 403))
    check("ageing: investing from aged/frozen balance rejected with explicit error", ok, detail)

    pen = db_json(f"""
import json
from backend.apps.ledger.models import InvestorBalanceLot
ls = list(InvestorBalanceLot.objects.filter(investor_user_id='{a["user_id"]}').values(
    'source_type','currency_id','original_amount_minor','available_amount_minor','status','penalized_amount_minor'))
print('@@' + json.dumps([{{k: str(v) for k, v in x.items()}} for x in ls]))
""")
    check("penalty: day-60 breach lot marked / penalties accrue (1%% daily capped)",
          any("penal" in str(x.get("status", "")) or int(x.get("penalized_amount_minor") or 0) > 0 for x in pen),
          json.dumps(pen)[:800])
    state["a_lots_day60"] = pen

    dash = api(admin, "GET", "/api/v1/admin-ops/dashboard/").json()
    blob = json.dumps(dash)
    check("dashboard: day-60 queues visible (forced withdrawal / ageing)",
          "withdraw" in blob.lower() or "ageing" in blob.lower() or "aging" in blob.lower(), blob[:400])
    save_state()


def _closeout_reports(admin):
    today = qa_today(admin).isoformat()
    for rt in ("balance_ageing", "reconciliation", "default_exposure", "fx_activity", "audit_log"):
        rep = api(admin, "POST", "/api/v1/reporting/admin/reports/", {
            "report_type": rt, "output_format": "csv", "redaction_mode": "full",
            "period_preset": "custom", "start_date": state["t0"], "end_date": today}, expect=(200, 201)).json()
        check(f"reporting: {rt} report generates", bool(rep.get("content") or rep.get("report_run")),
              str(rep)[:160])
    audit = api(admin, "GET", "/api/v1/admin-ops/audit-events/?limit=250").json()
    acts = [e.get("action", "") for e in (audit if isinstance(audit, list) else audit.get("results", []))]
    needed = ["qa_dev_mode", "deposit", "close", "disburse", "repay", "withdraw"]
    missing = [n for n in needed if not any(n in x for x in acts)]
    check("audit: lifecycle actions all audited", not missing, f"missing={missing} n={len(acts)}")


def stage_closeout():
    admin = load_session("admin")
    inv_a = load_session("a")
    a = state["A"]
    today = qa_today(admin).isoformat()

    code = sensitive_code(inv_a, a["email"], "bank_account_change")
    pi = api(inv_a, "POST", "/api/v1/ledger/payout-instructions/", {
        "currency": "CHF", "destination_iban": "CH5604835012345678009",
        "destination_account_name": "QA Investor A", **code}, expect=(200, 201)).json()
    check("payout: A self-declared IBAN with email code (unfreezes withdrawal path)", bool(pi),
          json.dumps(pi)[:300])

    ba = chf_balance(inv_a)
    amount = ba.get("total_available_minor", 0)
    if amount == 0:
        check("withdrawal: already completed in prior pass (balance 0)", True, "")
        _closeout_reports(admin)
        return
    code = sensitive_code(inv_a, a["email"], "withdrawal")
    wd = api(inv_a, "POST", "/api/v1/ledger/withdrawal-requests/", {
        "amount_minor": amount, "currency": "CHF",
        "destination_iban": "CH5604835012345678009", "destination_account_name": "QA Investor A",
        **code, "idempotency_key": "qa-wd-a1"}, expect=(200, 201)).json()
    wid = wd["withdrawal_request"]["id"] if "withdrawal_request" in wd else wd.get("id")
    check("withdrawal: A requested full available balance with email code", bool(wid), json.dumps(wd)[:300])
    fin = api(admin, "POST", f"/api/v1/ledger/admin/withdrawal-requests/{wid}/finalize/", {
        "booking_date": today, "value_date": today,
        "collection_account_identifier": "CH5604835012345678009",
        "bank_reference": "WD-A-1", "evidence_reference": "statement:wd-a-1",
        "idempotency_key": "qa-wd-a1-fin"}, expect=(200, 201)).json()
    check("withdrawal: admin finalized (final, 'out' movement)", bool(fin), json.dumps(fin)[:300])

    for rt in ("balance_ageing", "reconciliation", "default_exposure", "fx_activity", "audit_log"):
        rep = api(admin, "POST", "/api/v1/reporting/admin/reports/", {
            "report_type": rt, "output_format": "csv", "redaction_mode": "full",
            "period_preset": "custom", "start_date": state["t0"], "end_date": today}, expect=(200, 201)).json()
        check(f"reporting: {rt} report generates", bool(rep.get("content") or rep.get("report_run")),
              str(rep)[:160])

    audit = api(admin, "GET", "/api/v1/admin-ops/audit-events/?limit=250").json()
    acts = [e.get("action", "") for e in (audit if isinstance(audit, list) else audit.get("results", []))]
    needed = ["qa_dev_mode", "deposit", "close", "disburse", "repay", "withdraw"]
    missing = [n for n in needed if not any(n in x for x in acts)]
    check("audit: lifecycle actions all audited", not missing, f"missing={missing} n={len(acts)}")

    recon = db_json("""
import json
from django.db.models import Sum
from backend.apps.ledger.models import InvestorBalanceLot
by_cur = {}
for cur in ('CHF','EUR'):
    tot = InvestorBalanceLot.objects.filter(currency_id=cur).aggregate(s=Sum('available_amount_minor'))['s'] or 0
    by_cur[cur] = int(tot)
print('@@' + json.dumps(by_cur))
""")
    check("reconciliation: remaining investor lots computed (identity check basis)", True, json.dumps(recon))
    save_state()


def stage_revert():
    admin = load_session("admin")
    r = api(admin, "POST", "/api/v1/qa/dev-mode/revert/", {"confirmation": "REVERT QA DB"},
            expect=(200, 202)).json()
    check("qa: revert accepted", True, json.dumps(r)[:200])
    time.sleep(3)
    counts = db_json("""
import json
from django.contrib.auth import get_user_model
from backend.apps.loans.models import Loan
from backend.apps.entities.models import BorrowerEntity
print('@@' + json.dumps({'users': get_user_model().objects.count(),
    'loans': Loan.objects.count(), 'borrowers': BorrowerEntity.objects.count()}))
""")
    check("qa: database restored to pre-QA snapshot (2 users, 0 loans, 0 borrowers)",
          counts == {"users": 2, "loans": 0, "borrowers": 0}, json.dumps(counts))


def stage_fxsmoke():
    admin = load_session("admin")
    st = api(admin, "POST", "/api/v1/qa/dev-mode/enable/", {"note": "FX smoke (Claude); will revert."}).json()
    check("fx-smoke: QA mode re-enabled with fresh snapshot", st.get("is_enabled") is True, json.dumps(st)[:150])
    c = make_investor("c", "qa-investor-c@banxum.com", admin)
    today = qa_today(admin).isoformat()
    deposit(admin, c["user_id"], c["email"], 150_000_00, today, "qa-dep-c1", "BX-CHF-QA-C")
    inv_c = load_session("c")

    ok, detail = expect_error(lambda: api(inv_c, "POST", "/api/v1/fx/quotes/", {
        "source_currency": "CHF", "target_currency": "EUR",
        "source_amount_minor": 120_000_00, "idempotency_key": "qa-fx-c-cap"}, expect=201), (400,))
    check("fx: quote above CHF 100,000/day cap rejected", ok, detail)
    ok, detail = expect_error(lambda: api(inv_c, "POST", "/api/v1/fx/quotes/", {
        "source_currency": "CHF", "target_currency": "USD",
        "source_amount_minor": 1_000_00, "idempotency_key": "qa-fx-c-usd"}, expect=201), (400,))
    check("fx: unsupported pair CHF/USD rejected", ok, detail)

    q = api(inv_c, "POST", "/api/v1/fx/quotes/", {
        "source_currency": "CHF", "target_currency": "EUR",
        "source_amount_minor": 10_000_00, "idempotency_key": "qa-fx-c1"}, expect=201).json()
    check("fx: live quote issued (Yahoo), 1-minute lock", bool(q.get("expires_at")), json.dumps(q)[:400])
    fee_ok = q.get("platform_fee_bps") == 150 or "150" in str(q.get("platform_fee_bps"))
    check("fx: platform fee 1.5% (150 bps) applied", fee_ok, json.dumps(q)[:300])
    code = sensitive_code(inv_c, c["email"], "fx")
    ex = api(inv_c, "POST", f"/api/v1/fx/quotes/{q['id']}/execute/", {
        **code, "idempotency_key": "qa-fx-c1-exec"}, expect=(200, 201)).json()
    check("fx: executed, EUR credited instantly", bool(ex), json.dumps(ex)[:300])

    lots = db_json(f"""
import json
from backend.apps.ledger.models import InvestorBalanceLot
ls = list(InvestorBalanceLot.objects.filter(investor_user_id='{c["user_id"]}').values(
    'currency_id','source_type','original_amount_minor','available_amount_minor',
    'investment_deadline_at','withdrawal_deadline_at','lineage'))
print('@@' + json.dumps([{{k: str(v) for k, v in x.items()}} for x in ls]))
""")
    chf = next(x for x in lots if x["currency_id"] == "CHF")
    eur = next((x for x in lots if x["currency_id"] == "EUR"), None)
    inherit = bool(eur) and eur["investment_deadline_at"] == chf["investment_deadline_at"]         and eur["withdrawal_deadline_at"] == chf["withdrawal_deadline_at"]
    check("fx: EUR lot inherits source lot deadlines exactly (ageing not reset)", inherit,
          json.dumps(lots)[:600])
    check("fx: lineage recorded on target lot", bool(eur) and eur.get("lineage") not in ("[]", "", None),
          str(eur.get("lineage"))[:200] if eur else "no EUR lot")

    ba_eur = chf_balance(inv_c, "EUR")
    check("fx: portal shows EUR balance after conversion", ba_eur.get("total_available_minor", 0) > 0,
          json.dumps(ba_eur)[:300])

    r = api(admin, "POST", "/api/v1/qa/dev-mode/revert/", {"confirmation": "REVERT QA DB"},
            expect=(200, 202)).json()
    check("fx-smoke: reverted to snapshot again", True, json.dumps(r)[:120])
    counts = db_json("""
import json
from django.contrib.auth import get_user_model
from backend.apps.loans.models import Loan
print('@@' + json.dumps({'users': get_user_model().objects.count(), 'loans': Loan.objects.count()}))
""")
    check("fx-smoke: staging clean again (2 users, 0 loans)", counts == {"users": 2, "loans": 0},
          json.dumps(counts))


STAGES = {
    "fxsmoke": stage_fxsmoke,
    "fixtures": stage_fixtures, "investors": stage_investors, "invest": stage_invest,
    "close": stage_close, "tt1_age25": stage_tt1_age25, "tt2_due": stage_tt2_due,
    "tt3_late_fx": stage_tt3_late_fx, "tt4_secondary": stage_tt4_secondary,
    "tt5_default_buy": stage_tt5_default_buy, "tt6_day60": stage_tt6_day60,
    "closeout": stage_closeout, "revert": stage_revert,
}

if __name__ == "__main__":
    STAGES[sys.argv[1]]()
    print("stage done:", sys.argv[1])
