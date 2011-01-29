/* Definitions of some C99 math library functions, for those platforms
   that don't implement these functions already. */

int _pypy_math_isinf(double x);
int _pypy_math_isnan(double x);

double _pypy_math_acosh(double x);
double _pypy_math_asinh(double x);
double _pypy_math_atanh(double x);

double _pypy_math_expm1(double x);
double _pypy_math_log1p(double x);
