# Login System PRD

## Overview
The goal is to implement a secure user login system.

## Test Points
1. Users must be able to log in with a valid username and password.
2. Invalid login attempts should return a 401 Unauthorized status with a specific error message.
3. The system should lock the account after 5 consecutive failed login attempts.
4. A successful login should return a JWT token in the response body.
5. The JWT token should have an expiration time of 24 hours.

## UI Specifics
1. The login page should have a username field, a password field, and a submit button.
2. The password field should mask the input characters.
