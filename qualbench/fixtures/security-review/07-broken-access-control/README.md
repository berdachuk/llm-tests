Defect: broken access control / insecure direct object reference (IDOR)
-- the endpoint fetches an invoice by ID from the path with no check that
the invoice belongs to the currently authenticated user, letting any
logged-in user read any other user's invoice by guessing/incrementing
the ID.
