# Biometric Authentication API Documentation

## Overview

The biometric authentication system provides secure staff check-in/out functionality using fingerprints, Face ID, or PIN codes. All biometric data is encrypted and stored with salted hashing for enhanced security.

## Security Features

- **Salted Hashing**: Each biometric template is hashed with a unique salt
- **Encrypted Storage**: Biometric templates are encrypted before database storage
- **Indexed Lookups**: Database indexes ensure fast biometric matching
- **GDPR Compliance**: Designed with privacy regulations in mind

## API Endpoints

### 1. Fingerprint Enrollment

Enroll a staff member's fingerprint for authentication.

**Endpoint:** `POST /api/v1/staff/fingerprint/enroll`

**Headers:**
- `Authorization: Bearer {token}` (Required)

**Request Body:**
```json
{
  "staff_id": 123,
  "fingerprint_data": "base64_encoded_fingerprint_template",
  "device_id": "POS-001"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Fingerprint enrolled successfully for John Doe",
  "enrolled_at": "2024-02-08T10:30:00Z"
}
```

### 2. Face ID Enrollment

Enroll a staff member's face for authentication.

**Endpoint:** `POST /api/v1/staff/face/enroll`

**Headers:**
- `Authorization: Bearer {token}` (Required)

**Request Body:**
```json
{
  "staff_id": 123,
  "face_data": "base64_encoded_face_embeddings",
  "device_id": "POS-001"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Face ID enrolled successfully for John Doe",
  "enrolled_at": "2024-02-08T10:35:00Z"
}
```

### 3. Biometric Check-In/Out

Universal endpoint for checking in or out using any biometric method.

**Endpoint:** `POST /api/v1/staff/biometric/check-in`

**Request Body (Fingerprint):**
```json
{
  "fingerprint_data": "base64_encoded_fingerprint_template",
  "device_id": "POS-001",
  "location_lat": 40.7128,
  "location_lng": -74.0060
}
```

**Request Body (Face ID):**
```json
{
  "face_data": "base64_encoded_face_embeddings",
  "device_id": "POS-001",
  "location_lat": 40.7128,
  "location_lng": -74.0060
}
```

**Response:**
```json
{
  "success": true,
  "message": "John Doe checked in successfully",
  "staff_id": 123,
  "staff_name": "John Doe",
  "check_in_time": "2024-02-08T08:00:00Z",
  "method": "fingerprint"
}
```

### 4. PIN Setup

Set up a PIN code as an alternative authentication method.

**Endpoint:** `POST /api/v1/staff/pin/setup`

**Headers:**
- `Authorization: Bearer {token}` (Required)

**Request Body:**
```json
{
  "staff_id": 123,
  "pin": "1234"
}
```

**Response:**
```json
{
  "success": true,
  "message": "PIN set successfully"
}
```

### 5. PIN Check-In/Out

Check in or out using a PIN code.

**Endpoint:** `POST /api/v1/staff/pin/check-in`

**Request Body:**
```json
{
  "staff_id": 123,
  "pin": "1234",
  "device_id": "POS-001",
  "location_lat": 40.7128,
  "location_lng": -74.0060
}
```

**Response:**
```json
{
  "success": true,
  "message": "John Doe checked in successfully",
  "staff_id": 123,
  "staff_name": "John Doe",
  "check_in_time": "2024-02-08T08:00:00Z",
  "method": "pin"
}
```

### 6. Get Biometric Status

Check enrollment status for a staff member.

**Endpoint:** `GET /api/v1/staff/biometric/status/{staff_id}`

**Headers:**
- `Authorization: Bearer {token}` (Required)

**Response:**
```json
{
  "fingerprint_enrolled": true,
  "fingerprint_enrolled_at": "2024-02-01T10:00:00Z",
  "face_enrolled": false,
  "face_enrolled_at": null,
  "pin_set": true,
  "pin_updated_at": "2024-02-01T10:05:00Z"
}
```

## Error Responses

### 400 Bad Request
```json
{
  "detail": "Staff member not found"
}
```

### 401 Unauthorized
```json
{
  "detail": "Not authenticated"
}
```

### 403 Forbidden
```json
{
  "detail": "Not enough permissions"
}
```

## Data Models

### StaffBiometric

Stores encrypted biometric data with enhanced security:

- `staff_id`: Unique identifier for the staff member
- `fingerprint_template`: Encrypted fingerprint data with embedded salt
- `fingerprint_hash`: Salted hash for secure comparison
- `face_template`: Encrypted face embeddings with embedded salt
- `face_hash`: Salted hash for secure comparison
- `pin_hash`: Salted and hashed PIN with embedded salt
- `is_fingerprint_enabled`: Boolean flag for fingerprint status
- `is_face_enabled`: Boolean flag for Face ID status
- `is_pin_enabled`: Boolean flag for PIN status

### AttendanceLog

Records check-in/out events:

- `staff_id`: Reference to staff member
- `check_in`: Timestamp of check-in
- `check_out`: Timestamp of check-out
- `method`: Authentication method used (fingerprint, face, pin)
- `status`: Current status (checked_in, checked_out)
- `location_lat`: Latitude of check-in location
- `location_lng`: Longitude of check-in location
- `device_id`: Identifier of the device used

## Implementation Notes

1. **Biometric Template Format**: All biometric data should be base64 encoded before sending to the API
2. **Salt Storage**: Salts are embedded with the biometric templates using a separator
3. **Multiple Rounds**: Hashing uses 10,000 rounds for added security (PBKDF2-like approach)
4. **Location Tracking**: Optional location coordinates can be provided for compliance and security
5. **Device Tracking**: Device IDs help with security auditing and fraud detection

## Security Considerations

1. **HTTPS Required**: All biometric data must be transmitted over HTTPS
2. **Token Authentication**: All enrollment endpoints require valid JWT tokens
3. **Rate Limiting**: Implement rate limiting to prevent brute force attempts
4. **Audit Logging**: All biometric operations should be logged for security auditing
5. **Data Retention**: Follow GDPR guidelines for biometric data retention
6. **Access Control**: Only authorized managers should be able to enroll biometrics

## Migration from Legacy System

If migrating from a system without salted hashing:

1. The service will detect legacy data format
2. Legacy data will be logged with warnings
3. Consider re-enrolling biometrics for enhanced security
4. Gradual migration is supported - old and new formats can coexist