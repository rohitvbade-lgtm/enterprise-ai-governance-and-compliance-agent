# AI Model Usage Policy

**Policy Code:** POL-MOD-001  
**Category:** MODEL_USAGE  
**Severity:** HIGH  
**Version:** 1.0  
**Effective From:** 2024-01-01  
**Status:** ACTIVE

---

## Purpose

This policy governs the selection, approval, deployment, and ongoing monitoring of AI models used within organizational applications. It ensures that models are fit for purpose, risk-assessed, and operated within defined boundaries.

## Scope

Applies to all AI models deployed or accessed by the organization, including:
- Commercial LLM APIs (OpenAI, Anthropic, Google, Groq, etc.)
- Open-source models run locally (Ollama, self-hosted)
- Fine-tuned models derived from base models
- Embedding models
- Specialized task models (classification, summarization, etc.)

## Model Approval Process

Before deploying any AI model in a production environment, the following must be completed:

1. **Model Risk Assessment** — evaluate model capabilities, known failure modes, hallucination rates, and bias characteristics
2. **Data Privacy Review** — confirm the model provider's data handling practices (does inference data train the model?)
3. **Security Review** — assess model susceptibility to adversarial inputs
4. **Governance Board Approval** — formal sign-off for MEDIUM risk and above models

## Model Risk Tiers

| Tier | Description | Examples | Approval Required |
|---|---|---|---|
| LOW | Internal tools, closed systems, non-sensitive data | Developer coding assistant (internal code only) | Team lead |
| MEDIUM | Customer-facing, some sensitive data, broad capabilities | Customer support bot | Department head + Security |
| HIGH | Financial decisions, healthcare, HR, legal | Financial advisory, HR screening | CISO + DPO + Legal |
| CRITICAL | Automated decisions with legal effect | Credit decisions, medical triage | C-suite + Legal + External audit |

## Rules

### Rule 1: Approved Model Registry

Only models listed in the organization's approved model registry may be used in production AI applications. Use of unapproved models requires formal exception request.

**Violation Severity:** HIGH

### Rule 2: Provider Data Usage Restrictions

AI applications using external model providers MUST use providers that do not use customer inference data for model training, unless explicit user consent has been obtained. For sensitive data categories (PII, financial, health), only providers with signed Data Processing Agreements (DPAs) may be used.

**Violation Severity:** CRITICAL

### Rule 3: Model Version Pinning

Production AI applications MUST pin the specific model version in use. Automatic model updates that change behavior without review are prohibited.

**Violation Severity:** MEDIUM

### Rule 4: Hallucination Risk Controls

AI applications making factual claims or recommendations MUST implement hallucination mitigations including:
- Grounding responses in retrieved documents (RAG)
- Confidence indicators
- Human review for high-stakes outputs
- Disclaimer requirements where appropriate

**Violation Severity:** HIGH

### Rule 5: High-Risk Domain Restrictions

AI models deployed in the following domains require CRITICAL tier approval and ongoing monitoring:
- Financial advice or automated financial decisions
- Healthcare diagnosis or treatment recommendations
- Legal advice or automated legal decisions
- HR screening, performance assessment, or termination recommendations
- Law enforcement or security screening

**Violation Severity:** CRITICAL

### Rule 6: Model Performance Monitoring

All production AI models must have monitoring in place to detect:
- Output quality degradation
- Unexpected behavior changes (model drift)
- Increased error rates
- Security incident patterns

Monitoring reports must be reviewed quarterly.

**Violation Severity:** MEDIUM

### Rule 7: Fine-Tuning and Custom Models

Fine-tuned models require the same approval process as the base model tier, plus:
- Documentation of the fine-tuning dataset (source, consent, curation)
- Evaluation results on representative test sets
- Comparison against base model behavior

**Violation Severity:** HIGH

### Rule 8: Unapproved Model Fallback

If an approved model becomes unavailable, fallback to an unapproved model is not permitted. Applications must fail gracefully and alert operations rather than automatically switch to an unapproved model.

**Violation Severity:** MEDIUM

## Compliance Requirements

- EU AI Act (Risk-based classification)
- NIST AI RMF (Map 1.5, Measure 2.5)
- ISO 42001 — AI Management System
- SEBI/RBI guidelines for financial AI (if applicable)

## Remediation Guidance

1. Maintain an up-to-date model registry with version, provider, risk tier, and approval status.
2. Implement model version locking in all production deployments.
3. Establish quarterly model review process with security and compliance teams.
4. Build fallback and degraded mode behavior for model unavailability.
5. Document all fine-tuning datasets and their governance status.

---

*Policy Owner: Chief AI Officer / Head of Engineering*  
*Last Reviewed: 2024-01-01*

