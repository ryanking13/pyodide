#ifndef JS2PYTHON_H
#define JS2PYTHON_H

/**
 * Translate JavaScript objects to Python objects.
 */
#include "Python.h"
#include "jslib.h"

/**
 * Convert a JavaScript object to a Python object.
 *  \param x The JavaScript object.
 *  \return The Python object resulting from the conversion. Returns NULL and
 *    sets the Python error indicator if a conversion error occurs.
 */
PyObject*
js2python(JsVal x);

PyObject*
js2python_immutable(JsVal x);

/**
 * Like js2python and js2python_immutable, but also set *kind to JS_KIND_PYPROXY
 * if x is a PyProxy and to 0 otherwise. This saves a pyproxy_Check call for
 * callers that need to destroy a borrowed PyProxy after converting it.
 */
PyObject*
js2python_kind(JsVal x, int* kind);

PyObject*
js2python_immutable_kind(JsVal x, int* kind);

PyObject*
js2python_convert(JsVal x, int depth, JsVal defaultConverter);

/** Initialize any global variables used by this module. */
int
js2python_init();

extern int compat_null_to_none;

#endif /* JS2PYTHON_H */
