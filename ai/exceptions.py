class LlamaDisabledError(Exception):
    pass

class LlamaModelNotFoundError(FileNotFoundError):
    pass

class LlamaNotInstalledError(ImportError):
    pass
