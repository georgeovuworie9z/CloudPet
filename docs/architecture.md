CloudPet — Architecture Specification
1. Purpose
CloudPet is a production-style pet management REST API used as a hands-on AWS cloud engineering portfolio project.
The project deliberately separates application engineering from cloud infrastructure engineering:
* Claude Code: backend implementation
* Human developer: AWS architecture and implementation
* ChatGPT: architecture, technical leadership, review, troubleshooting, and learning support
2. Architectural Goals
The system should demonstrate:
* REST API design
* relational database design
* authentication and authorization
* containerization
* AWS networking
* high availability
* scalable application deployment
* object storage
* IAM least privilege
* observability
* CI/CD
* infrastructure as code
The initial implementation should remain simple enough to understand and operate.
3. Logical Application Architecture
Client
  |
  v
FastAPI API
  |
  +--> Authentication / Authorization
  |
  +--> API Routes
          |
          v
       Services
          |
          v
      Repositories
          |
          v
     PostgreSQL
4. Target AWS Architecture
                         INTERNET
                            |
                            v
                 Application Load Balancer
                            |
                  +---------+---------+
                  |                   |
                  v                   v
              EC2-A               EC2-B
           FastAPI/Docker       FastAPI/Docker
                  |                   |
                  +---------+---------+
                            |
                            v
                    RDS PostgreSQL

                    +---------------+
                    |      S3       |
                    | Pet Images    |
                    +---------------+

              CloudWatch / IAM / VPC
The final high-availability design should span at least two Availability Zones.
5. Network Architecture
Target VPC:
VPC
|
+-- Availability Zone A
|   +-- Public Subnet
|   +-- Private Application Subnet
|
+-- Availability Zone B
    +-- Public Subnet
    +-- Private Application Subnet
Expected responsibilities:
* Public subnets: internet-facing ALB and required public networking components
* Private application subnets: EC2 application instances
* Database subnets: RDS in private subnets
* Internet Gateway: internet connectivity for public resources
* NAT Gateway: outbound internet access for private resources where required
* Route tables: explicit traffic control
The human developer will implement and validate this architecture manually before converting it to Terraform.
6. Security Group Model
Traffic should follow:
Internet
   |
   v
ALB-SG
   |
   v
EC2-SG
   |
   v
RDS-SG
Rules should be based on security-group relationships where practical.
Do not expose PostgreSQL to the public internet.
7. Application Runtime
The FastAPI service must be stateless.
This is required because multiple instances will eventually run behind an ALB.
Do not rely on:
* local server session state
* local filesystem persistence
* in-memory state that must be shared between instances
Persistent data belongs in PostgreSQL or S3.
8. Database
Primary database:
* PostgreSQL
* SQLAlchemy ORM
* Alembic migrations
Core entities:
User
  |
  +----< Pet
            |
            +----< MedicalRecord
            |
            +----< PetEvent
            |
            +----< PetImage
9. Object Storage
Pet images are stored in S3.
PostgreSQL stores metadata such as:
* object key
* original file name
* content type
* associated pet
* timestamps
Target flow:
Client
  |
  | request upload authorization
  v
FastAPI
  |
  | presigned URL
  v
Client
  |
  | upload directly
  v
S3
The exact presigned-upload implementation is a later application milestone.
10. Authentication
MVP uses application-managed JWT authentication.
Flow:
Client
  |
  | credentials
  v
FastAPI
  |
  +--> verify password against PostgreSQL
  |
  v
JWT
  |
  v
Client
Future version may evaluate Amazon Cognito.
11. Authorization
Ownership is a core security boundary.
Example:
User A
  |
  +-- Pet A

User B
  |
  +-- Pet B
User A must not be able to retrieve, modify, delete, or manage records belonging to Pet B.
Authorization must be enforced server-side.
12. Health and Availability
GET /health should provide a lightweight application health response.
The endpoint will eventually be used by the ALB target group.
A future readiness endpoint may validate required dependencies such as database connectivity.
13. Observability
CloudWatch will eventually collect:
* application logs
* request errors
* authentication failures
* database-related errors
* ALB target health
* ALB request count
* ALB response latency
* EC2 CPU/status
* RDS CPU
* RDS storage
* RDS connections
14. Deployment Evolution
Stage 1 — Local
Docker Compose
  |
  +-- FastAPI
  |
  +-- PostgreSQL
Stage 2 — AWS manual deployment
Internet
  |
 ALB
  |
 EC2
  |
 RDS
Stage 3 — High availability
Internet
  |
 ALB
  |
 +---- EC2-A
 |
 +---- EC2-B
       |
      RDS
Stage 4 — CI/CD
GitHub
  |
GitHub Actions
  |
Tests
  |
Docker Build
  |
ECR
  |
Deployment
Stage 5 — Infrastructure as Code
Terraform will reproduce the AWS infrastructure after the human developer understands the manual architecture.
15. Architecture Principles
* Least privilege
* Defense in depth
* Stateless application servers
* Private database
* No hardcoded secrets
* Explicit ownership authorization
* Reproducible migrations
* Automated testing
* Observable production behavior
* Incremental complexity
16. Future Extensions
Potential CloudPet v2 features:
* Amazon Cognito
* notifications
* messaging
* location-aware communities using coarse location
* lost/found pets
* pet events and community features
* mobile application
* serverless event processing
* queues/event bus