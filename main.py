from Simulator import *
import sys

args = sys.argv
if len(args) != 2:
    print("Usage: ./program_name [input json]")

input_file = args[1]

print(f"Executing simulation of {input_file}\n")
sim = Simulator(input_file)
sim.run()
