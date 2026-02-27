import codecs
try:
    with codecs.open("stdout-rightpupil.txt", "r", "utf-16le") as f:
        lines = f.readlines()
        
        # print last 150 lines
        for line in lines[-150:]:
            print(line.rstrip())
except Exception as e:
    print(f"Error reading file: {e}")
