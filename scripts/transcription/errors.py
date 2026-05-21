class TranscriptionError(Exception):
    pass


class ProviderConfigError(TranscriptionError):
    pass


class ArtifactStoreError(TranscriptionError):
    pass


class ProviderExecutionError(TranscriptionError):
    pass
