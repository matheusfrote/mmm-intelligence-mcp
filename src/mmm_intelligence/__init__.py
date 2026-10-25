"""Independent, local and exploratory MMM tools."""

import os

for _thread_variable in ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS"):
    os.environ[_thread_variable] = "1"

__version__ = "0.2.0"
