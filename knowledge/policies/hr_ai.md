# HR AI Governance Policy

**Policy Code:** POL-HR-001  
**Category:** HR / REGULATORY  
**Severity:** HIGH  
**Version:** 1.0  
**Effective From:** 2024-01-01  
**Status:** ACTIVE

---

## Purpose

This policy governs the use of AI in human resources (HR) contexts, including recruitment, performance assessment, employee monitoring, compensation decisions, and workforce planning. It protects employee rights, prevents discriminatory outcomes, and ensures compliance with employment laws.

## Scope

Applies to all AI applications used in:
- Resume screening and candidate ranking
- Interview scheduling and analysis
- Performance evaluation and scoring
- Workforce analytics and people analytics
- Employee engagement monitoring
- Compensation and benefits decisions
- Promotion and succession planning
- Termination recommendations

## Principles

AI in HR must uphold:
- **Fairness:** No discriminatory outcomes based on protected characteristics
- **Transparency:** Employees must know when AI is used in decisions affecting them
- **Human Oversight:** AI recommendations must not replace human judgment in consequential decisions
- **Privacy:** Employee data must be protected with the highest level of care

## Rules

### Rule 1: No Autonomous HR Decisions

AI systems MUST NOT autonomously make final decisions on hiring, termination, promotion, or significant compensation changes. AI may rank, score, or recommend, but a qualified human reviewer must make and document the final decision.

**Violation Severity:** CRITICAL

### Rule 2: Transparency to Employees

Employees and candidates must be informed when AI tools are used in processes affecting their employment. This disclosure must occur before data collection and must include the purpose of the AI tool and how the output will be used.

**Violation Severity:** HIGH

### Rule 3: Protected Characteristic Exclusion

HR AI applications MUST NOT use, directly or indirectly, any protected characteristics in decision-making including:
- Race, ethnicity, color, national origin
- Gender, gender identity, sexual orientation
- Age (except where legally required)
- Disability status
- Religion
- Pregnancy or parental status
- Marital status

Proxy variables that correlate with protected characteristics (certain postcodes, names, school affiliations) must also be excluded.

**Violation Severity:** CRITICAL

### Rule 4: Bias Assessment Requirement

All HR AI models must undergo bias assessment before deployment using diverse test datasets. Bias assessments must be repeated annually and after significant model updates.

**Violation Severity:** HIGH

### Rule 5: Employee Data Minimization

HR AI applications must collect and process only the employee data strictly necessary for the defined purpose. Behavioral surveillance beyond legitimate business need is prohibited.

**Violation Severity:** HIGH

### Rule 6: Employee Data Protection

Employee data including salary, performance records, health information, disciplinary records, and personal information is CRITICAL sensitivity data. It must be:
- Encrypted at rest and in transit
- Access-controlled to authorized HR roles
- Not shared with AI providers without DPA
- Retained only within policy-defined periods

**Violation Severity:** CRITICAL

### Rule 7: Right to Explanation

Employees and candidates subject to AI-assisted decisions have the right to request an explanation of how the AI system influenced the decision. HR departments must be able to provide this explanation in plain language.

**Violation Severity:** HIGH

### Rule 8: Monitoring and Surveillance Limits

AI-based employee monitoring must be:
- Disclosed to employees
- Limited to legitimate business purposes (productivity, security)
- Not used to monitor protected activities (union organizing, whistleblowing)
- Subject to Works Council / employee representative review where applicable

**Violation Severity:** HIGH

### Rule 9: Governance Approval for HR AI Deployment

All AI applications used in HR decision processes must receive governance approval including:
- HR leadership sign-off
- Legal review (employment law compliance)
- Bias assessment results review
- Data Protection Officer review

**Violation Severity:** HIGH

## Compliance Requirements

- EU AI Act (High-Risk AI — Annex III: employment and workers management)
- GDPR Article 22 — Automated Individual Decision-Making
- Equal Employment Opportunity laws
- DPDP Act 2023 (India)
- Applicable local employment laws

## Remediation Guidance

1. Classify all HR AI applications as HIGH risk minimum.
2. Implement human-in-the-loop for all final employment decisions.
3. Remove or anonymize protected characteristic data from model inputs.
4. Conduct annual fairness audits with external review.
5. Establish employee grievance process for AI-affected decisions.
6. Maintain an AI impact assessment for each HR AI application.

---

*Policy Owner: Chief People Officer / HR Compliance Lead*  
*Last Reviewed: 2024-01-01*

