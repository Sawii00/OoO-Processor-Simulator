# Cycle-by-Cycle Simulator of an Out-of-Order Processor

This is the final submission for the first Lab of CS-470 (Advanced Computer Architecture) at EPFL. 
The goal was to implement a cycle-by-cycle accurate simulation of a MIPS R10000-inspired OoO processor running a subset of RISCV ISA, including all the internal structures such as Active List, Integer Queue, Register Renaming structures, etc. Moreover, we had to support Precise Exception Handling. 

To run a test it is sufficient to invoke the program as:
```
./main.py [name of test case file]
```


The program will output in the same directory of main.py a file called out_299307_[name of test case file].json

Report: https://drive.google.com/file/d/1KyqphLyF5sUgaBUKodo8FXF5ul2LFJm1/view?usp=sharing
