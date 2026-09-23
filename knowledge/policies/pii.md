# PII & Data Privacy Policy

**Policy Code:** POL-PII-001  
**Category:** PII / DATA_PRIVACY  
**Severity:** CRITICAL  
**Version:** 1.0  
**Effective From:** 2024-01-01  
**Status:** ACTIVE

---

## Purpose

This policy defines requirements for the handling, detection, and protection of Personally Identifiable Information (PII) and sensitive personal data within AI applications operated by the organization.

## Scope

This policy applies to all AI applications that process, generate, store, or transmit data that could identify individuals, including but not limited to customer data, employee data, and partner data.

## Definitions

**PII (Personally Identifiable Information):** Any data that can be used to directly or indirectly identify a person, including but not limited to:
- Full name
- Email addresses
- Phone numbers
- Government-issued identification numbers (Aadhaar, PAN, SSN, Passport)
- Financial account numbers and credit card numbers
- Biometric data
- IP addresses
- Device identifiers
- Location data

**Sensitive Personal Data:** PII that when disclosed creates elevated risk of harm:
- Health and medical information
- Financial information
- Authentication credentials (passwords, API keys, tokens)
- Racial or ethnic origin
- Religious beliefs

## Rules

### Rule 1: No Raw PII in AI Model Inputs

AI applications MUST NOT transmit raw PII to external AI model providers without explicit data processing agreements and user consent. All PII must be masked, tokenized, or redacted before submission to external LLM APIs.

**Violation Severity:** CRITICAL

### Rule 2: PII Detection at Ingestion

All AI applications that accept user input MUST implement PII detection at the point of ingestion. Detected PII must trigger governance review before processing continues.

**Violation Severity:** HIGH

### Rule 3: Aadhaar and PAN Protection

Aadhaar numbers (12-digit Indian national ID) and PAN numbers (10-character Indian tax ID) are classified as CRITICAL sensitive data. Detection of these identifiers in AI input/output MUST result in immediate BLOCK or escalation.

**Violation Severity:** CRITICAL

### Rule 4: Credit Card Data Prohibition

AI applications are prohibited from storing, logging, or processing full credit card numbers (PAN numbers in payment context). Partial masking (e.g., last 4 digits) is permitted only for display purposes.

**Violation Severity:** CRITICAL

### Rule 5: Credential Exposure Prevention

AI applications MUST detect and block the processing or generation of authentication credentials including passwords, API keys, private keys, and session tokens.

**Violation Severity:** CRITICAL

### Rule 6: Data Minimization

AI applications MUST request and process only the minimum personal data required to fulfill the specified business purpose.

**Violation Severity:** MEDIUM

### Rule 7: Audit Trail for PII Events

Every detection of PII in AI input or output must be recorded in the immutable audit log with the finding type, severity, and redacted evidence (no raw PII in logs).

**Violation Severity:** HIGH

## Compliance Requirements

- GDPR (General Data Protection Regulation)
- DPDP Act 2023 (India Digital Personal Data Protection Act)
- PCI-DSS (for payment card data)
- ISO 27001

## Remediation Guidance

1. Implement regex-based PII detection before forwarding input to LLMs.
2. Mask detected PII using placeholder tokens (e.g., `[EMAIL_REDACTED]`).
3. Raise a governance finding for each PII type detected.
4. Request human review for CRITICAL PII findings.
5. Maintain a data processing register for all AI applications handling PII.

## Exceptions

Exceptions to this policy require:
- Written approval from the Data Protection Officer (DPO)
- Documented mitigation controls
- Time-bound exception with maximum 90-day validity
- Quarterly review

---

*Policy Owner: Data Protection Officer*  
*Last Reviewed: 2024-01-01*

