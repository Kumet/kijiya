class KijiyaError(Exception):
    user_message: str

    def __init__(self, user_message: str):
        self.user_message = user_message
        super().__init__(user_message)


class UnsafeUrlError(KijiyaError):
    pass


class FetchError(KijiyaError):
    pass


class TooLargeError(KijiyaError):
    pass


class UnsupportedContentError(KijiyaError):
    pass


class ExtractionError(KijiyaError):
    pass


class GenerationError(KijiyaError):
    pass


class RateLimitError(KijiyaError):
    pass
