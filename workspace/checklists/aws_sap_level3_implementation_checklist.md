# AWS Certified Solutions Architect Professional (SAP-C02)
## Implementation Checklist for Codex

**Goal:** Create a study/implementation checklist covering all exam domains and task statements for the AWS Solutions Architect Professional certification.

---

## 📋 Domain 1: Design for Organizational Complexity (12.5%)

### 1.1 Architect Network Connectivity Strategies
- [ ] VPC design: CIDR ranges, subnets (public/private/transit)
- [ ] AWS Direct Connect configuration
- [ ] VPN connectivity (Site-to-Site, Client VPN)
- [ ] Transit Gateway architecture
- [ ] VPC peering vs Transit Gateway decision matrix
- [ ] DNS design (Route 53, private hosted zones)

### 1.2 Prescribe Security Controls
- [ ] IAM policies (JSON structure, least privilege)
- [ ] Security groups & NACLs
- [ ] AWS Config rules
- [ ] Service Control Policies (SCPs)
- [ ] KMS keys & encryption strategies
- [ ] WAF & Shield configuration

### 1.3 Design Reliable & Resilient Architectures
- [ ] Multi-AZ strategies
- [ ] RDS multi-AZ vs read replicas
- [ ] Elasticache replication
- [ ] DynamoDB global tables
- [ ] S3 replication (CRR/SRR)
- [ ] Route 53 health checks & failover

---

## 📋 Domain 2: Design for New Solutions (30%)

### 2.1 Determine Cross-Account Authentication & Access Strategy
- [ ] IAM roles for cross-account access
- [ ] AWS Organizations & SCPs
- [ ] Resource Access Manager (RAM)
- [ ] IAM Identity Center (SSO)
- [ ] Security Token Service (STS)

### 2.2 Determine Networking Architecture
- [ ] PrivateLink for service access
- [ ] VPC endpoints (Gateway vs Interface)
- [ ] Network Load Balancer architecture
- [ ] API Gateway private endpoints
- [ ] VPC Lattice
- [ ] App Mesh / Cloud Map for service discovery

### 2.3 Determine Compute Architecture
- [ ] EC2 instance types selection (compute optimized, memory optimized, etc.)
- [ ] Auto Scaling groups (dynamic, scheduled, predictive)
- [ ] Lambda architecture & limits
- [ ] ECS/EKS container strategies
- [ ] Fargate vs EC2 decision matrix
- [ ] Batch computing (AWS Batch)

### 2.4 Determine Storage Architecture
- [ ] S3 tiering (Standard, IA, Glacier, Intelligent-Tiering)
- [ ] EBS volume types (gp3, gp2, io2, st1, sc1)
- [ ] EFS vs FSx for file storage
- [ ] S3 Glacier Vault Lock
- [ ] Data lake architecture on S3

### 2.5 Determine Database Architecture
- [ ] RDS instance selection &Aurora architecture
- [ ] DynamoDB (provisioned vs on-demand)
- [ ] ElastiCache strategies (Redis vs Memcached)
- [ ] DocumentDB / MongoDB compatibility
- [ ] Neptune for graph databases
- [ ] Keyspaces (Cassandra)
- [ ] Timestream (time-series)
- [ ] QLDB (ledger)

### 2.6 Determine Application Architecture
- [ ] Event-driven (EventBridge, SQS, SNS)
- [ ] API design patterns (REST, GraphQL)
- [ ] Microservices communication (sync vs async)
- [ ] Step Functions for workflows
- [ ] AppSync for GraphQL
- [ ] SQS dead-letter queue handling
- [ ] Kinesis for real-time streaming

### 2.7 Determine Security Architecture
- [ ] IAM roles vs users vs groups
- [ ] Secrets Manager integration
- [ ] Parameter Store for configuration
- [ ] GuardDuty & Security Hub
- [ ] Inspector for vulnerability scanning
- [ ] Private certificate authority

---

## 📋 Domain 3: Migration Planning (15%)

### 3.1 Assess Migration Readiness
- [ ] Migration Evaluator (formerly TSO Logic)
- [ ] Application Discovery Service
- [ ] Database Migration Service (DMS)
- [ ] Schema Conversion Tool (SCT)

### 3.2 Determine Migration Strategy
- [ ] 6 R's: Rehost, Replatform, Repurchase, Refactor, Retain, Retire
- [ ] Wave planning & migration Factory
- [ ] Velocity planning (migration waves)
- [ ] Dependency mapping

### 3.3 Determine Migration Tools
- [ ] AWS Migration Hub
- [ ] Server Migration Service (SMS)
- [ ] Database Migration Service (DMS)
- [ ] DataSync for large data transfers
- [ ] Transfer Family for SFTP

---

## 📋 Domain 4: Cost Control (12.5%)

### 4.1 Determine Cost-Effective Compute Solutions
- [ ] EC2 Savings Plans vs Reserved Instances
- [ ] Spot Instances & interruption handling
- [ ] Lambda cost optimization
- [ ] ECS/EKS cost controls (Fargate vs EC2)
- [ ] Auto Scaling for cost efficiency

### 4.2 Determine Cost-Effective Storage Solutions
- [ ] S3 lifecycle policies
- [ ] S3 Intelligent-Tiering
- [ ] EBS snapshots automation
- [ ] Glacier storage class selection
- [ ] EFS/FSx cost comparison

### 4.3 Determine Cost-Effective Database Solutions
- [ ] RDS reserved instances
- [ ] DynamoDB on-demand vs provisioned
- [ ] Aurora Serverless
- [ ] ElastiCache reserved nodes

### 4.4 Design Cost-Effective Networking
- [ ] NAT Gateway cost optimization
- [ ] Direct Connect for sustained usage
- [ ] VPC traffic mirroring costs
- [ ] CloudFront caching to reduce data transfer

---

## 📋 Domain 5: Continuous Improvement for Existing Solutions (30%)

### 5.1 Determine Security Architecture Improvements
- [ ] IAM Access Analyzer
- [ ] Security Hub compliance standards
- [ ] Detective vs Preventive controls
- [ ] Incident response automation
- [ ] Encryption at rest vs in transit

### 5.2 Determine Resiliency Improvements
- [ ] Disaster Recovery strategies (RTO/RPO)
- [ ] DR architecture (pilot light, warm standby, multi-region)
- [ ] Backup strategies & automation
- [ ] Chaos engineering (Fault Injection Simulator)

### 5.3 Determine Performance Improvements
- [ ] CloudFront distribution optimization
- [ ] ElastiCache/DB query caching
- [ ] RDS performance insights
- [ ] Lambda cold start mitigation
- [ ] S3 transfer acceleration

### 5.4 Determine Operational Improvements
- [ ] CloudWatch dashboards & alarms
- [ ] Systems Manager for patch management
- [ ] Config rules for compliance
- [ ] Service Catalog for self-service
- [ ] CodePipeline for CI/CD

### 5.5 Determine Cost Optimization Improvements
- [ ] Cost Explorer rightsizing recommendations
- [ ] Lambda concurrent execution monitoring
- [ ] S3 analytics for storage class decisions
- [ ] Compute Optimizer recommendations
- [ ] AWS Budgets & alerts

---

## 🎯 High-Priority Focus Areas (From Exam Perspective)

1. **Event-Driven Architecture** — Heavy emphasis on EventBridge, SQS, Lambda
2. **Multi-Account Strategy** — Organizations, SCPs, Control Tower
3. **Security** — IAM least privilege, KMS, Secrets Manager, PrivateLink
4. **DR & Resilience** — RTO/RPO, multi-region, failover patterns
5. **Cost Optimization** — Savings Plans, Spot, S3 lifecycle, rightsizing
6. **Migration** — DMS, SCT, 6 R's, dependency mapping
7. **Networking** — Transit Gateway, PrivateLink, VPC endpoints
8. **Database** — Aurora, DynamoDB, ElastiCache strategies
9. **Container Strategy** — ECS/EKS, Fargate, ECR
10. **Serverless** — Lambda, Step Functions, AppSync, EventBridge

---

## 📚 Recommended Resources

- AWS SAP-C02 Exam Guide (official)
- AWS Well-Architected Framework (Cost, Security, Reliability, Performance, Operational Excellence)
- AWS Solutions Library (reference architectures)
- Tutorials Dojo practice exams
- Jon Bonso / Tutorials Dojo practice tests

---

*Last updated: 2026-02-28*
*Generated for: Heath (jeebs)*
