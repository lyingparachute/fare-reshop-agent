class SetupError(Exception):
    def __init__(self, *, error: str, reason: str, fix: str) -> None:
        super().__init__(error)
        self.error = error
        self.reason = reason
        self.fix = fix
