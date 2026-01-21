from dataclasses import dataclass
from typing import List, Dict

@dataclass
class AgnoDocument:
    content: str
    metadata: Dict
