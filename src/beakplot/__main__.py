"""Allow python -m beakplot as well as the installed beakplot command."""

from .cli import main

raise SystemExit(main())
