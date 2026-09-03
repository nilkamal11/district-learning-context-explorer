from __future__ import annotations

import json

from district_context.illinois_profile import build_north_palos_profile

if __name__ == "__main__":
    print(json.dumps(build_north_palos_profile(), indent=2))
