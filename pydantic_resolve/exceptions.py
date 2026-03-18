class ResolverTargetAttrNotFound(Exception):
    pass

class LoaderFieldNotProvidedError(Exception):
    pass

class MissingAnnotationError(Exception):
    pass

class GlobalLoaderFieldOverlappedError(Exception):
    pass

class MissingCollector(Exception):
    pass

class LoaderContextNotProvidedError(Exception):
    """Raised when a DataLoader requires context but Resolver doesn't provide one."""
    pass