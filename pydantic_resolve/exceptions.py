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


class DuplicateErConfigError(Exception):
    pass


class DuplicateRelationshipError(Exception):
    pass


class InvalidRelationshipError(Exception):
    pass