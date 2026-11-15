"""pyfakefs teardown for modules that bind pathlib.Path at import.

A test that first imports perf.analysis.e2_resources while the fake
filesystem is active (`from perf.analysis import e2_resources` inside
resource_facts) binds that module's Path to the fake class. pyfakefs then
drops the module from sys.modules and leaves it on the parent package.
The next `from perf.analysis import e2_resources` returns that object, and
Path still points at a patcher that has already been torn down.

Reloading the module on the way in and on the way out rebinds Path. The
dotted import of e2_typing reimports itself after the sys.modules drop;
e2_resources does not, because the parent package attribute short-circuits
that import.
"""

import pytest
from pyfakefs.fake_filesystem_unittest import Patcher

from perf.analysis import e2_resources

_RELOAD = [e2_resources]


@pytest.fixture
def fs(request):
    if hasattr(request, "param"):
        patcher = Patcher(*request.param)
        extra = list(_RELOAD)
        if patcher.modules_to_reload:
            patcher.modules_to_reload.extend(extra)
        else:
            patcher.modules_to_reload = extra
    else:
        patcher = Patcher(modules_to_reload=list(_RELOAD))
    patcher.setUp()
    yield patcher.fs
    patcher.tearDown()
