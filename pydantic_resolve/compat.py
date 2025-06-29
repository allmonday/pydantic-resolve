import sys
from pydantic.version import VERSION as P_VERSION

PYDANTIC_VERSION = P_VERSION
PYDANTIC_V2 = PYDANTIC_VERSION.startswith("2.")


OVER_PYTHON_3_7 = sys.version_info[1] >= 7