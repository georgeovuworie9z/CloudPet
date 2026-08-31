CloudPet — API Specification v1.0
1. API Overview
CloudPet exposes a versioned REST API.
Base path:
/api/v1
Primary content type:
application/json
Authentication:
Authorization: Bearer <JWT>
2. API Conventions
Use standard HTTP methods:
* GET: retrieve
* POST: create
* PUT: replace/update
* DELETE: remove
Use appropriate status codes:
* 200 OK
* 201 Created
* 204 No Content
* 400 Bad Request
* 401 Unauthorized
* 403 Forbidden
* 404 Not Found
* 409 Conflict
* 422 Unprocessable Entity
* 500 Internal Server Error
Error responses should use a consistent JSON structure and must not expose stack traces, SQL details, secrets, or internal implementation information.
3. Authentication
Register
POST /api/v1/auth/register
Request:
{
  "email": "user@example.com",
  "password": "secure-password",
  "first_name": "John",
  "last_name": "Doe",
  "phone": "+4512345678"
}
Expected behavior:
* validate email
* validate password requirements
* reject duplicate email
* hash password
* create user
Return the created user representation without the password hash.
Login
POST /api/v1/auth/login
Request:
{
  "email": "user@example.com",
  "password": "secure-password"
}
Return an access token.
Current authenticated user
GET /api/v1/auth/me
Requires authentication.
4. Users
Get current profile
GET /api/v1/users/me
Requires authentication.
Update current profile
PUT /api/v1/users/me
Requires authentication.
Users may update only their own profile.
Delete current account
DELETE /api/v1/users/me
Requires authentication.
Deletion behavior must be explicitly handled with regard to owned pets and related records. Do not silently introduce destructive cascading behavior without documenting it.
5. Pets
Create pet
POST /api/v1/pets
Requires authentication.
Example:
{
  "name": "Max",
  "species": "dog",
  "breed": "Labrador",
  "sex": "male",
  "date_of_birth": "2022-05-12",
  "weight": 28.5,
  "description": "Friendly and energetic."
}
The authenticated user becomes the owner.
List current user’s pets
GET /api/v1/pets
Requires authentication.
Only pets owned by the authenticated user should be returned.
Future query parameters may support:
* species
* breed
* search
* pagination
Get pet
GET /api/v1/pets/{pet_id}
Requires authentication and ownership authorization.
Update pet
PUT /api/v1/pets/{pet_id}
Requires authentication and ownership authorization.
Delete pet
DELETE /api/v1/pets/{pet_id}
Requires authentication and ownership authorization.
6. Medical Records
Create record
POST /api/v1/pets/{pet_id}/medical-records
Requires authentication and pet ownership.
Example:
{
  "record_type": "vaccination",
  "description": "Annual vaccination",
  "veterinarian": "City Vet Clinic",
  "record_date": "2026-08-20"
}
List records
GET /api/v1/pets/{pet_id}/medical-records
Requires authentication and pet ownership.
Get record
GET /api/v1/pets/{pet_id}/medical-records/{record_id}
Requires authentication and ownership.
Update record
PUT /api/v1/pets/{pet_id}/medical-records/{record_id}
Requires authentication and ownership.
Delete record
DELETE /api/v1/pets/{pet_id}/medical-records/{record_id}
Requires authentication and ownership.
7. Pet Events
Create event
POST /api/v1/pets/{pet_id}/events
Example:
{
  "event_type": "vet_appointment",
  "title": "Annual checkup",
  "description": "Routine examination",
  "event_date": "2026-09-15T10:00:00Z"
}
List events
GET /api/v1/pets/{pet_id}/events
Get event
GET /api/v1/pets/{pet_id}/events/{event_id}
Update event
PUT /api/v1/pets/{pet_id}/events/{event_id}
Delete event
DELETE /api/v1/pets/{pet_id}/events/{event_id}
All event operations require authentication and ownership authorization.
8. Pet Images
Initial API:
POST /api/v1/pets/{pet_id}/images
GET /api/v1/pets/{pet_id}/images
DELETE /api/v1/pets/{pet_id}/images/{image_id}
The production target is secure S3 object storage.
Preferred later upload flow:
Client
  |
  | request upload
  v
API
  |
  | generate presigned URL
  v
Client
  |
  | upload directly
  v
S3
Do not make the S3 bucket publicly writable.
9. Health
GET /health
Expected response:
{
  "status": "healthy"
}
This endpoint should be lightweight and suitable for ALB health checks.
10. Data Model
User
id
email
password_hash
first_name
last_name
phone
created_at
updated_at
is_active
Pet
id
owner_id
name
species
breed
sex
date_of_birth
weight
description
created_at
updated_at
MedicalRecord
id
pet_id
record_type
description
veterinarian
record_date
created_at
updated_at
PetEvent
id
pet_id
event_type
title
description
event_date
created_at
updated_at
PetImage
id
pet_id
object_key
file_name
content_type
created_at
11. Validation Requirements
Validate:
* email format
* password requirements
* required fields
* string lengths
* allowed enum-like values
* dates and timestamps
* numeric ranges such as weight
* resource identifiers
Do not trust client-supplied ownership identifiers.
The authenticated user’s identity determines ownership.
12. Authorization Requirements
Every protected pet-related endpoint must verify:
1. the request is authenticated
2. the referenced resource exists
3. the authenticated user owns the resource
Nested resources such as medical records and events must inherit authorization through their associated pet.
13. Pagination
List endpoints should be designed so pagination can be added cleanly.
The initial implementation may use a simple limit/offset model.
Do not load unbounded collections from the database.
14. API Documentation
FastAPI’s generated OpenAPI documentation should remain available in development.
Expected documentation endpoints:
/docs
/redoc
/openapi.json
Production exposure can be reviewed later as part of security hardening.
15. Testing Requirements
At minimum, tests should cover:
Authentication
* successful registration
* duplicate registration
* successful login
* invalid credentials
* authenticated user retrieval
Pets
* create
* list
* retrieve
* update
* delete
* unauthenticated access
* unauthorized access to another user’s pet
Medical records
* create
* retrieve
* update
* delete
* ownership enforcement
Events
* create
* retrieve
* update
* delete
* ownership enforcement
Health
* successful health response
16. Future API Extensions
Potential future endpoints:
/api/v1/notifications
/api/v1/messages
/api/v1/pet-events
/api/v1/lost-pets
/api/v1/locations
These are explicitly outside the MVP.
