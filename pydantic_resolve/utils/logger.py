import logging

def setup_library_logger():
    library_logger = logging.getLogger('pydantic_resolve')
    library_logger.addHandler(logging.NullHandler())
    return library_logger
