# CSA STAR Level 3 Implementation Checklist
## Cloud Security Alliance + Continuous Monitoring Readiness

**Note:** CSA STAR Level 3 (continuous monitoring certification) is still being defined by CSA. AWS states "CSA is still defining the Level 3 Continuous Monitoring requirements, so there is no available certification to determine alignment." This checklist builds toward Level 3 readiness based on CCM v4.1 (207 controls, 17 domains) and continuous monitoring capabilities.

---

## 📋 CSA STAR Overview

| Level | Type | Description |
|-------|------|-------------|
| **Level 1** | Self-assessment | Submit CAIQ (Consensus Assessments Initiative Questionnaire) |
| **Level 2** | Third-party certification | STAR Certification via accredited assessors |
| **Level 3** | Continuous monitoring | Ongoing automated compliance (in development) |

---

## 📋 Domain 1: Application & Interface Security (AIS)

- [ ] API security (authentication, rate limiting, input validation)
- [ ] Application vulnerability scanning
- [ ] Secure software development lifecycle (SSDLC)
- [ ] Code review & static analysis
- [ ] OWASP Top 10 mitigation
- [ ] Web Application Firewall (WAF) deployment

---

## 📋 Domain 2: Audit Assurance & Compliance (AAC)

- [ ] Audit logging & retention policy
- [ ] Compliance monitoring automation
- [ ] Evidence collection automation
- [ ] Internal audit schedule & scope
- [ ] Third-party audit engagement (for Level 2)
- [ ] Continuous compliance dashboard

---

## 📋 Domain 3: Business Continuity Management & Operational Resilience (BCR)

- [ ] Business continuity plan (BCP)
- [ ] Disaster recovery plan (DRP)
- [ ] RTO/RPO definitions
- [ ] Backup automation & testing
- [ ] Chaos engineering / fault injection
- [ ] Incident response plan & playbook

---

## 📋 Domain 4: Change Control & Configuration Management (CCM)

- [ ] Infrastructure as Code (IaC) security scanning
- [ ] Configuration management database (CMDB)
- [ ] Change approval process
- [ ] Drift detection
- [ ] Immutable infrastructure patterns
- [ ] Patch management automation

---

## 📋 Domain 5: Data Security & Information Lifecycle Management (DSI)

- [ ] Data classification framework
- [ ] Encryption at rest (KMS, customer-managed keys)
- [ ] Encryption in transit (TLS 1.2+)
- [ ] Data masking/tokenization
- [ ] Data retention & disposal policies
- [ ] DLP deployment
- [ ] Secrets management (AWS Secrets Manager, HashiCorp Vault)

---

## 📋 Domain 6: Datacenter Security (DCS)

- [ ] Physical security controls (for on-prem/colocation)
- [ ] Access control & monitoring
- [ ] Environmental controls
- [ ] Redundancy & resilience
- [ ] Asset inventory

---

## 📋 Domain 7: Encryption & Key Management (EKM)

- [ ] Key management policy
- [ ] KMS architecture (AWS KMS, CloudHSM)
- [ ] Key rotation automation
- [ ] HSM usage for sensitive keys
- [ ] Key access logging & monitoring

---

## 📋 Domain 8: Governance & Risk Management (GRM)

- [ ] Information security policy
- [ ] Risk register & assessment process
- [ ] Vendor risk management
- [ ] Security governance structure
- [ ] Compliance framework mapping (CCM, ISO 27001, SOC 2)
- [ ] Board/leadership reporting

---

## 📋 Domain 9: Human Resources (HRS)

- [ ] Background checks
- [ ] Security awareness training
- [ ] Acceptable use policy
- [ ] Role-based access control (RBAC)
- [ ] Termination process
- [ ] Security responsibilities in job descriptions

---

## 📋 Domain 10: Identity & Access Management (IAM)

- [ ] IAM policy (least privilege)
- [ ] MFA enforcement
- [ ] Federated identity (SAML, OIDC)
- [ ] Privileged access management (PAM)
- [ ] Access reviews & certification
- [ ] Service account management
- [ ] Just-in-time (JIT) access

---

## 📋 Domain 11: Interoperability & Portability (IPY)

- [ ] API standardization (REST, GraphQL)
- [ ] Data portability formats
- [ ] Multi-cloud / hybrid considerations
- [ ] Vendor lock-in assessment
- [ ] Export capabilities

---

## 📋 Domain 12: Mobile Security (MOS)

- [ ] Mobile device management (MDM)
- [ ] Mobile application security
- [ ] BYOD policy
- [ ] Mobile containerization
- [ ] App store security requirements

---

## 📋 Domain 13: Security Incident Management, E-Discovery & Cloud Forensics (SIM)

- [ ] Incident response plan
- [ ] SIEM deployment (security event correlation)
- [ ] Log aggregation & retention
- [ ] Forensic readiness
- [ ] E-discovery procedures
- [ ] Chain of custody

---

## 📋 Domain 14: Supply Chain Management, Transparency & Risk Management (STR)

- [ ] Vendor assessment process
- [ ] SLA requirements
- [ ] Supply chain visibility
- [ ] Third-party security requirements
- [ ] Sub-processor tracking

---

## 📋 Domain 15: Threat & Vulnerability Management (TVM)

- [ ] Vulnerability scanning
- [ ] Penetration testing
- [ ] Threat intelligence integration
- [ ] Security patching
- [ ] Threat modeling
- [ ] Bug bounty program (optional)

---

## 📋 Domain 16: User & Entity Behavior Analytics (UEBA)

- [ ] Behavioral baseline establishment
- [ ] Anomaly detection
- [ ] User activity monitoring
- [ ] Insider threat detection
- [ ] Alert tuning & response

---

## 📋 Domain 17: Virtualization & Containers Security (VCS)

- [ ] Hypervisor security
- [ ] Container runtime security
- [ ] Container orchestration security (ECS/EKS)
- [ ] Image scanning (ECR, Trivy)
- [ ] Network segmentation (micro-segmentation)
- [ ] Workload isolation

---

## 🎯 Level 3 Readiness: Continuous Monitoring

Since Level 3 is still being formalized, these capabilities position you for continuous monitoring certification:

### Automation Requirements
- [ ] Automated evidence collection
- [ ] Continuous compliance scanning
- [ ] Automated remediation
- [ ] Real-time alerting
- [ ] Dashboard & reporting automation
- [ ] API-based control testing

### Monitoring Stack
- [ ] Cloud-native monitoring (CloudWatch, GuardDuty, Security Hub)
- [ ] SIEM integration
- [ ] Configuration monitoring (AWS Config, CloudTrail)
- [ ] Threat detection (GuardDuty, Inspector)
- [ ] Log aggregation (centralized logging)
- [ ] Performance + security correlation

### Integration
- [ ] CAIQ automation
- [ ] CCM control mapping to infrastructure
- [ ] Policy-as-code enforcement
- [ ] Audit API readiness
- [ ] Continuous self-assessment capability

---

## 📋 STAR Level 1 → Level 2 → Level 3 Progression

| Milestone | Level 1 | Level 2 | Level 3 |
|-----------|---------|---------|---------|
| CAIQ submission | ✅ | ✅ | ✅ |
| Third-party audit | | ✅ | ✅ |
| Continuous monitoring | | | ✅ |
| Automated evidence | | | ✅ |
| Real-time compliance | | | ✅ |

---

## 📚 Resources

- CSA Cloud Controls Matrix (CCM) v4.1: cloudsecurityalliance.org/research/cloud-controls-matrix
- CSA STAR Program: cloudsecurityalliance.org/research/star
- CAIQ (Consensus Assessments Initiative Questionnaire)
- CCM v4.1: 207 controls across 17 domains

---

*Last updated: 2026-02-28*
*Generated for: Heath (jeebs)*
