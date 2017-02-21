"""Component unittests."""
from __future__ import division

import numpy
import unittest

from six import assertRaisesRegex

from openmdao.api import Problem, ExplicitComponent, IndepVarComp
from openmdao.test_suite.components.expl_comp_simple import TestExplCompSimple
from openmdao.test_suite.components.expl_comp_array import TestExplCompArray
from openmdao.test_suite.components.impl_comp_simple import TestImplCompSimple
from openmdao.test_suite.components.impl_comp_array import TestImplCompArray
from openmdao.devtools.testutil import assert_rel_error


class TestExplicitComponent(unittest.TestCase):

    def test___init___simple(self):
        """Test a simple explicit component."""
        comp = TestExplCompSimple()
        prob = Problem(comp).setup(check=False)

        # check optional metadata (desc)
        self.assertEqual(comp._var2meta['length']['desc'],
                         'length of rectangle')
        self.assertEqual(comp._var2meta['width']['desc'],
                         'width of rectangle')
        self.assertEqual(comp._var2meta['area']['desc'],
                         'area of rectangle')

        prob['length'] = 3.
        prob['width'] = 2.
        prob.run_model()
        assert_rel_error(self, prob['area'], 6.)

    def test___init___array(self):
        """Test an explicit component with array inputs/outputs."""
        comp = TestExplCompArray(thickness=1.)
        prob = Problem(comp).setup(check=False)

        prob['lengths'] = 3.
        prob['widths'] = 2.
        prob.run_model()
        assert_rel_error(self, prob['total_volume'], 24.)

    def test_error_handling(self):
        """Test error handling when adding inputs/outputs."""
        comp = ExplicitComponent()

        msg = "Incompatible shape for '.*': Expected (.*) but got (.*)"

        with assertRaisesRegex(self, ValueError, msg):
            comp.add_output('arr', val=numpy.ones((2,2)), shape=([2]))

        with assertRaisesRegex(self, ValueError, msg):
            comp.add_input('arr', val=numpy.ones((2,2)), shape=([2]))

        msg = "Shape of indices does not match shape for '.*': Expected (.*) but got (.*)"

        with assertRaisesRegex(self, ValueError, msg):
            comp.add_input('arr', val=numpy.ones((2,2)), src_indices=[0,1])


class TestImplicitComponent(unittest.TestCase):

    def test___init___simple(self):
        """Test a simple implicit component."""
        x = -0.5
        a = numpy.abs(numpy.exp(0.5 * x) / x)

        comp = TestImplCompSimple()
        prob = Problem(comp).setup(check=False)

        prob['a'] = a
        prob.run_model()
        assert_rel_error(self, prob['x'], x)

    def test___init___array(self):
        """Test an implicit component with array inputs/outputs."""
        comp = TestImplCompArray()
        prob = Problem(comp).setup(check=False)

        prob['rhs'] = numpy.ones(2)
        prob.run_model()
        assert_rel_error(self, prob['x'], numpy.ones(2))


if __name__ == '__main__':
    unittest.main()
