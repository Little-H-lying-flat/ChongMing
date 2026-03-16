import py_compile
try:
    py_compile.compile(r'app\engines\right_pupil\__init__.py', doraise=True)
    print("OK")
except py_compile.PyCompileError as e:
    print(f"Error Type: {type(e.exc_value)}")
    print(f"Error Msg: {e.exc_value.msg}")
    print(f"Error Line: {e.exc_value.lineno}")
