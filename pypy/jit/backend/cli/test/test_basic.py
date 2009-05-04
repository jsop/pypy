import py
from pypy.jit.backend.cli.runner import CliCPU
from pypy.jit.metainterp.test import test_basic

class CliJitMixin(test_basic.OOJitMixin):
    CPUClass = CliCPU

class TestBasic(CliJitMixin, test_basic.BasicTests):
    # for the individual tests see
    # ====> ../../../metainterp/test/test_basic.py

    def skip(self):
        py.test.skip("works only after translation")

    def _skip(self):
        py.test.skip("in-progress")

    test_string = skip
    test_chr2str = skip
    test_unicode = skip
    test_residual_call = skip
    test_constant_across_mp = skip
    
    test_stopatxpolicy = _skip
    test_we_are_jitted = _skip
    test_format = _skip
    test_r_uint = _skip
    test_getfield = _skip
    test_getfield_immutable = _skip
    test_mod_ovf = _skip
    test_print = _skip
    test_bridge_from_interpreter = _skip
    test_bridge_from_interpreter_2 = _skip
    test_bridge_from_interpreter_3 = _skip
    test_bridge_from_interpreter_4 = _skip
    test_instantiate_classes = _skip
    test_zerodivisionerror = _skip
