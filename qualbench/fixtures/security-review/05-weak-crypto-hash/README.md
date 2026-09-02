Defect: passwords are hashed with unsalted MD5 before storage instead of
a proper password-hashing algorithm (bcrypt/scrypt/Argon2/PBKDF2), making
them trivially crackable via rainbow tables/brute force.
