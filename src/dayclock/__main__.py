"""Allow python -m dayclock as well as the installed dayclock command."""

from .cli import main

raise SystemExit(main())
