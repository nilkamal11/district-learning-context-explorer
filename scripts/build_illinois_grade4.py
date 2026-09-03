from __future__ import annotations

import json

from district_context.illinois_grade4 import build_grade4_extract

if __name__ == "__main__":
    print(json.dumps(build_grade4_extract(), indent=2))
