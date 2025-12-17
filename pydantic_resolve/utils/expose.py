from dataclasses import dataclass

@dataclass
class ExposeInfo:
    alias: str

def ExposeAs(alias: str) -> ExposeInfo:
    return ExposeInfo(alias=alias)