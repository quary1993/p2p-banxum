from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile


class LegalTemplateImportError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ImportedLenderAgreementTemplate:
    title: str
    body: str
    checkbox_label: str
    source_docx_sha256: str
    body_sha256: str
    version_label: str
    effective_date: str
    skipped_instruction_text: str
    unresolved_placeholders: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ImportedProjectInvestmentConfirmationTemplate:
    title: str
    body: str
    checkbox_label: str
    source_docx_sha256: str
    body_sha256: str
    version_label: str
    effective_date: str
    skipped_instruction_text: str
    unresolved_placeholders: tuple[str, ...]


WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = f"{{{WORD_NS}}}"
UNRESOLVED_PLACEHOLDER_RE = re.compile(r"\[(?:to be completed|to confirm|to complete)\]", re.I)

PROJECT_INVESTMENT_PLACEHOLDERS = {
    "[AGREEMENT_NO]": "{{order.agreement_no}}",
    "[CONFIRMATION_DATETIME]": "{{order.confirmation_datetime}}",
    "[PROJECT_ID]": "{{loan.id}}",
    "[PROJECT_NAME]": "{{loan.title}}",
    "[BORROWER_NAME]": "{{borrower.legal_name}}",
    "[BORROWER_ID]": "{{borrower.id}}",
    "[LOAN_AGREEMENT_NO]": "{{loan.agreement_no}}",
    "[LENDER_ID]": "{{lender.id}}",
    "[HOLDING_ID]": "{{holding.id}}",
    "[ASSIGNOR_NAME]": "{{assignment.assignor_name}}",
    "[AMOUNT]": "{{order.amount}}",
    "[CURRENCY]": "{{order.currency}}",
    "[CLAIM_PRICE]": "{{order.claim_price}}",
    "[INTEREST_RATE]": "{{loan.interest_rate_percent}}",
    "[MATURITY_DATE]": "{{loan.maturity_date}}",
    "[bullet / amortising / monthly interest / other]": "{{loan.repayment_type}}",
    "[none / as described in the Project Summary / as per Collateral Documents]": (
        "{{loan.collateral_security}}"
    ),
    "[No / Yes, by whom / N/A]": "{{loan.buyback_obligation}}",
}


def _node_text(element: ElementTree.Element) -> str:
    chunks: list[str] = []
    for node in element.iter():
        if node.tag == f"{W}t":
            chunks.append(node.text or "")
        elif node.tag == f"{W}tab":
            chunks.append("\t")
        elif node.tag == f"{W}br":
            chunks.append("\n")
    return "".join(chunks).strip()


def _table_rows(table: ElementTree.Element) -> list[list[str]]:
    rows: list[list[str]] = []
    for row in table.findall(f"{W}tr"):
        cells: list[str] = []
        for cell in row.findall(f"{W}tc"):
            cells.append(re.sub(r"\s+", " ", _node_text(cell)).strip())
        if any(cells):
            rows.append(cells)
    return rows


def _format_table(rows: list[list[str]]) -> list[str]:
    if not rows:
        return []
    width = max(len(row) for row in rows)
    normalized = [row + [""] * (width - len(row)) for row in rows]
    lines = ["Table:"]
    for row in normalized:
        lines.append(" | ".join(cell if cell else "-" for cell in row))
    return lines


def _document_blocks(path: Path) -> list[str]:
    try:
        with ZipFile(path) as archive:
            document_xml = archive.read("word/document.xml")
    except Exception as exc:
        raise LegalTemplateImportError("Could not read DOCX document.xml.") from exc

    try:
        root = ElementTree.fromstring(document_xml)
    except ElementTree.ParseError as exc:
        raise LegalTemplateImportError("DOCX document.xml is not valid XML.") from exc

    body = root.find(f"{W}body")
    if body is None:
        raise LegalTemplateImportError("DOCX document body was not found.")

    blocks: list[str] = []
    for child in body:
        if child.tag == f"{W}p":
            text = _node_text(child)
            if text:
                blocks.append(text)
        elif child.tag == f"{W}tbl":
            rows = _table_rows(child)
            table_lines = _format_table(rows)
            if table_lines:
                blocks.append("\n".join(table_lines))
    return blocks


def _quoted_checkbox_label(text: str) -> str:
    cleaned = text.strip().strip("\"“”").strip()
    return cleaned


def extract_lender_user_agreement_template(
    *,
    docx_path: str | Path,
    effective_date: str,
) -> ImportedLenderAgreementTemplate:
    path = Path(docx_path)
    if not path.exists():
        raise LegalTemplateImportError(f"DOCX file does not exist: {path}")
    if path.suffix.lower() != ".docx":
        raise LegalTemplateImportError("Lender agreement source must be a .docx file.")
    effective_date = effective_date.strip()
    if not effective_date:
        raise LegalTemplateImportError("Effective date is required.")

    source_bytes = path.read_bytes()
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    raw_blocks = _document_blocks(path)
    if not raw_blocks:
        raise LegalTemplateImportError("DOCX file did not contain any importable text.")

    body_blocks: list[str] = []
    skipped_blocks: list[str] = []
    checkbox_label = ""
    skipping_instructions = False
    version_label = ""

    for index, block in enumerate(raw_blocks):
        normalized = re.sub(r"\s+", " ", block).strip().lower()
        if normalized.startswith("version:") and not version_label:
            version_label = block.splitlines()[0].replace("Version:", "").strip()

        if normalized == "recommended clickwrap acceptance wording":
            skipping_instructions = True
            skipped_blocks.append(block)
            continue

        if normalized == "main agreement":
            skipping_instructions = False
            body_blocks.append(block)
            continue

        if skipping_instructions:
            skipped_blocks.append(block)
            if not checkbox_label and index > 0 and block.startswith(("“", '"')):
                checkbox_label = _quoted_checkbox_label(block)
            continue

        body_blocks.append(block)

    if not checkbox_label:
        checkbox_label = (
            "I have read, understood and accept the General Terms and Conditions / "
            "User Agreement, including its integral annexes"
        )
    if not version_label:
        version_label = "0.4"

    body = "\n\n".join(body_blocks).replace("[to be completed]", effective_date)
    body = body.replace("\u00a0", " ")
    body_sha256 = hashlib.sha256(body.encode("utf-8")).hexdigest()
    unresolved = tuple(sorted(set(UNRESOLVED_PLACEHOLDER_RE.findall(body))))
    title = "General Terms and Conditions / User Agreement for Lenders"

    return ImportedLenderAgreementTemplate(
        title=title,
        body=body,
        checkbox_label=checkbox_label,
        source_docx_sha256=source_hash,
        body_sha256=body_sha256,
        version_label=version_label,
        effective_date=effective_date,
        skipped_instruction_text="\n\n".join(skipped_blocks),
        unresolved_placeholders=unresolved,
    )


def _replace_project_investment_placeholders(body: str) -> str:
    for source, target in PROJECT_INVESTMENT_PLACEHOLDERS.items():
        body = body.replace(source, target)
    return body


def extract_project_investment_confirmation_template(
    *,
    docx_path: str | Path,
    effective_date: str,
) -> ImportedProjectInvestmentConfirmationTemplate:
    path = Path(docx_path)
    if not path.exists():
        raise LegalTemplateImportError(f"DOCX file does not exist: {path}")
    if path.suffix.lower() != ".docx":
        raise LegalTemplateImportError(
            "Project investment confirmation source must be a .docx file."
        )
    effective_date = effective_date.strip()
    if not effective_date:
        raise LegalTemplateImportError("Effective date is required.")

    source_bytes = path.read_bytes()
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    raw_blocks = _document_blocks(path)
    if not raw_blocks:
        raise LegalTemplateImportError("DOCX file did not contain any importable text.")

    body_blocks: list[str] = []
    skipped_blocks: list[str] = []
    checkbox_label = ""
    skipping_confirmation = False
    version_label = ""

    for block in raw_blocks:
        normalized = re.sub(r"\s+", " ", block).strip().lower()
        if normalized.startswith("version:") and not version_label:
            first_line = block.splitlines()[0]
            version_label = first_line.split("|", maxsplit=1)[0].replace("Version:", "").strip()

        if normalized == "recommended confirmation text":
            skipping_confirmation = True
            skipped_blocks.append(block)
            continue

        if normalized == "part i - basic terms and conditions":
            skipping_confirmation = False
            body_blocks.append(block)
            continue

        if skipping_confirmation:
            skipped_blocks.append(block)
            if not checkbox_label:
                text = re.sub(r"^table:\s*", "", block, flags=re.I).strip()
                if text:
                    checkbox_label = _quoted_checkbox_label(text)
            continue

        body_blocks.append(block)

    if not checkbox_label:
        checkbox_label = (
            "I confirm this investment and accept the Project Investment Confirmation "
            "and Claim Assignment Agreement."
        )
    if not version_label:
        version_label = "0.4"

    body = "\n\n".join(body_blocks).replace("[to be completed]", effective_date)
    body = _replace_project_investment_placeholders(body)
    body = body.replace("\u00a0", " ")
    body_sha256 = hashlib.sha256(body.encode("utf-8")).hexdigest()
    unresolved = tuple(sorted(set(UNRESOLVED_PLACEHOLDER_RE.findall(body))))
    title = "Project Investment Confirmation and Claim Assignment Agreement"

    return ImportedProjectInvestmentConfirmationTemplate(
        title=title,
        body=body,
        checkbox_label=checkbox_label,
        source_docx_sha256=source_hash,
        body_sha256=body_sha256,
        version_label=version_label,
        effective_date=effective_date,
        skipped_instruction_text="\n\n".join(skipped_blocks),
        unresolved_placeholders=unresolved,
    )
