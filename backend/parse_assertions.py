import codecs

def parse_log():
    try:
        with codecs.open('stdout-rightpupil.txt', 'r', 'utf-16le') as f:
            lines = f.readlines()
            
        print("Parsing assertions from right pupil run:")
        for line in lines:
            line = line.strip()
            if "Final Report:" in line:
                try:
                    import ast
                    report_str = line.split("Final Report:")[1].strip()
                    report = ast.literal_eval(report_str)
                    print("👉 Report Items:")
                    for item in report:
                        print(f"   - {item}")
                    break
                except Exception as eval_e:
                    print(f"Eval Error: {eval_e}")
    except Exception as e:
        print(f"Error parsing log: {e}")

if __name__ == "__main__":
    parse_log()
