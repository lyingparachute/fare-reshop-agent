class ProviderAuthenticationError(Exception):
    def __init__(self) -> None:
        super().__init__("the provider rejected the API key")


class ProviderPermissionError(Exception):
    def __init__(self) -> None:
        super().__init__("the API key may not use the configured model")


class ProviderModelNotFoundError(Exception):
    def __init__(self) -> None:
        super().__init__("the provider does not know the configured model")


type ProviderRefusal = (
    ProviderAuthenticationError | ProviderPermissionError | ProviderModelNotFoundError
)
PROVIDER_REFUSALS = (
    ProviderAuthenticationError,
    ProviderPermissionError,
    ProviderModelNotFoundError,
)
