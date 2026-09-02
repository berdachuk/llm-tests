Defect: path traversal -- a user-supplied filename is concatenated
directly into a filesystem path with no validation, allowing
`../../etc/passwd`-style escapes outside the intended directory.
