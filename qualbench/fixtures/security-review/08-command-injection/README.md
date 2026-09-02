Defect: OS command injection -- a user-supplied filename is interpolated
directly into a shell command string executed via a shell (`shell=True`
/ `os.system`), allowing arbitrary shell command execution via shell
metacharacters (`;`, `|`, `&&`, backticks, etc.).
