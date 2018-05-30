.. index:: BalanceComp Example

.. _balancecomp_feature:

***********
BalanceComp
***********

`BalanceComp` is a specialized implementation of `ImplicitComponent` that
is intended to provide a simple way to implement most implicit equations
without the need to define your own residuals.

`BalanceComp` allows you to add one or more state variables and its associated
implicit equations.  For each ``balance`` added to the component it
solves the following equation:

.. math::

    f_{mult}(x) \cdot f_{lhs}(x) = f_{rhs}(x)

The following inputs and outputs are associated with each implicit state.

=========== ======= ====================================================
Name        I/O     Description
=========== ======= ====================================================
{name}      output  implicit state variable
lhs:{name}  input   left-hand side of equation to be balanced
rhs:{name}  input   right-hand side of equation to be balanced
mult:{name} input   left-hand side multiplier of equation to be balanced
=========== ======= ====================================================

The right-hand side is optional and will default to zero if not connected.
The multiplier is optional and will default to 1.0 if not connected. The
left-hand side should always be defined and should be dependent upon the value
of the implicit state variable.

The BalanceComp supports vectorized implicit states, simply provide a default
value or shape when adding the balance that reflects the correct shape.

BalanceComp accepts the following other arguments (which are all passed
to ``add_balance`` during initialization):

=========== ======================== ===================================================================================
Name        Type                     Description
=========== ======================== ===================================================================================
eq_units    str or None              Units associated with left-hand and right-hand side. (mult is treated as unitless).
lhs_name    str or None              Optional name associated with the left-hand side of the balance.
rhs_name    str or None              Optional name associated with the right-hand side of the balance.
rhs_val     int, float, or np.array  Default value for the right-hand side.
guess_func  callable or None         Callable function that returns an initial “guess” value of the state variable.
use_mult    bool                     Specifies whether the left-hand side multiplier is to be used.
mult_name   str or None              Optional name associated with the left-hand side multiplier variable.
mult_val    int, float, or np.array  Default value for the left-hand side multiplier.
kwargs      dict or named arguments  Additional arguments to be passed for the creation of the implicit state variable.
=========== ======================== ===================================================================================

Example:  Scalar Root Finding
-----------------------------

The following example uses a BalanceComp to implicitly solve the
equation:

.. math::

    2 \cdot x^2 = 4

Here, our LHS is connected to a computed value for :math:`x^2`, the multiplier is 2, and the RHS
is 4.  The expected solution is :math:`x=\sqrt{2}`.  We initialize :math:`x` with a value of 1 so that
it finds the positive root.

.. embed-code::
    openmdao.components.tests.test_balance_comp.TestBalanceComp.test_feature_scalar
    :layout: interleave

Alternatively, we could simplify the code by using the :code:`mult_val` argument.

.. embed-code::
    openmdao.components.tests.test_balance_comp.TestBalanceComp.test_feature_scalar_with_default_mult
    :layout: interleave


Example:  Vectorized Root Finding
---------------------------------

The following example uses a BalanceComp to implicitly solve the equation:

.. math::

    b \cdot x + c  = 0

for various values of :math:`b`, and :math:`c`.  Here, our LHS is connected to a computed value of
the linear equation.  The multiplier is one and the RHS is zero (the defaults), and thus
they need not be connected.

.. embed-code::
    openmdao.components.tests.test_balance_comp.TestBalanceComp.test_feature_vector
    :layout: interleave


Example:  Providing an Initial Guess for a State Variable
---------------------------------------------------------

As mentioned above, there is an optional argument to :code:`add_balance` called :code:`guess_func` which can
provide an initial guess for a state variable.

The Kepler example script shows how :code:`guess_func` can be used.

.. embed-code::
    openmdao.test_suite.test_examples.test_keplers_equation.TestKeplersEquation.test_result
    :layout: interleave

.. tags:: BalanceComp, Component
