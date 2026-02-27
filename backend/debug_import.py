import traceback
try:
    import app.main
    print("OK")
except Exception as e:
    traceback.print_exc()
