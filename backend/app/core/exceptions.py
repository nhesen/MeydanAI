class DomainError(Exception):
    def __init__(self, *, status: int, title: str, detail: str, error_code: str) -> None:
        super().__init__(detail)
        self.status = status
        self.title = title
        self.detail = detail
        self.error_code = error_code
